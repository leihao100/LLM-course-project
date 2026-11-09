import argparse
import csv
import hashlib
import json
from pathlib import Path

from .analysis import paired_cluster_bootstrap, summarize
from .audit import audit
from .core import FAULTS, TASKS, digest, kind
from .fixtures import synthetic_snapshots
from .original import ROOT
from .runner import run_grid
from .sandbox import export_snapshots, ordered
from .validation import preflight


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_snapshots(path):
    path = Path(path)
    expected = path.with_suffix(path.suffix + ".sha256")
    if not expected.exists():
        raise ValueError("Snapshot checksum file missing. Export or attest the source first.")
    if expected.read_text().strip() != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("Snapshot checksum mismatch")
    data = json.loads(path.read_text())
    ids = set()
    for snapshot in data:
        case = snapshot["case"]
        if case["id"] in ids:
            raise ValueError("Duplicate task ID")
        ids.add(case["id"])
        if kind(case) not in TASKS:
            raise ValueError("Task outside scoped evaluation")
        if snapshot["source"]["type"] not in ("benchmark_snapshot", "synthetic_fixture"):
            raise ValueError("Unknown snapshot source type")
        resources = ordered(snapshot["resources"])
        keys = [(r["resourceType"], r["id"]) for r in resources]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate resource IDs")
        snapshot["resources"] = resources
    return data


def main():
    parser = argparse.ArgumentParser(description="Chart corruption research harness (stdlib only)")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("audit")
    a.add_argument("--output", default="results/audit.json")
    d = sub.add_parser("demo")
    d.add_argument("--output", default="results/demo")
    p = sub.add_parser("plan")
    p.add_argument("--output", default="data/run_plan.csv")
    p.add_argument("--tasks", default=str(ROOT / "vendor/tasks_original.json"))
    ex = sub.add_parser("export")
    ex.add_argument("--fhir-url", required=True)
    ex.add_argument("--output", required=True)
    ex.add_argument("--provenance", required=True, help="Image digest and benchmark revision")
    r = sub.add_parser("run")
    r.add_argument("--snapshots", required=True)
    r.add_argument("--config", required=True)
    r.add_argument("--output", required=True)
    v = sub.add_parser("validate")
    v.add_argument("--snapshots", required=True)
    v.add_argument("--policy", default=str(ROOT / "configs/policy.json"))
    v.add_argument("--output", default="results/preflight.json")
    an = sub.add_parser("analyze")
    an.add_argument("--records", required=True)
    an.add_argument("--output", required=True)
    an.add_argument("--paired", action="store_true")
    args = parser.parse_args()
    if args.command == "audit":
        result = audit()
        write_json(args.output, result)
        print(f"Verified {len(result['findings'])} original-source findings; saved {args.output}")
    elif args.command == "demo":
        config = json.loads((ROOT / "configs/demo.json").read_text())
        config["policy"] = json.loads((ROOT / config.pop("policy_file")).read_text())
        rows = run_grid(synthetic_snapshots(), config, Path(args.output) / "records", deterministic=True)
        write_json(Path(args.output) / "summary.json", summarize(rows))
        print(f"{len(rows)} combinations, {sum(r['status']=='not_applicable' for r in rows)} N/A. Synthetic programmed controls only.")
    elif args.command == "plan":
        cases = [c for c in json.loads(Path(args.tasks).read_text()) if kind(c) in TASKS]
        rows = [{"case_id": c["id"], "task_type": kind(c), "patient_id": c["eval_MRN"],
                 "model_slot": model, "arm": arm, "fault": fault, "seed": 0,
                 "applicable": not (fault == "unit_convert" and TASKS[kind(c)] != "MG")}
                for c in cases for model in ("small", "medium", "large")
                for arm in ("baseline", "evidence_prompt") for fault in FAULTS]
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(json.dumps({"tasks": len(cases), "nominal": len(rows), "eligible": sum(r['applicable'] for r in rows),
                          "unique_patients": len({c['eval_MRN'] for c in cases})}))
    elif args.command == "export":
        cases = [c for c in json.loads((ROOT / "vendor/tasks_original.json").read_text()) if kind(c) in TASKS]
        n = export_snapshots(args.fhir_url, cases, args.output, args.provenance)
        print(f"Exported {n} read-only snapshots and checksum. No FHIR resources changed.")
    elif args.command == "validate":
        result = preflight(load_snapshots(args.snapshots), json.loads(Path(args.policy).read_text()))
        write_json(args.output, result)
        print(json.dumps({k: v for k, v in result.items() if k != "cases"}))
    elif args.command == "run":
        config_path = Path(args.config)
        config = json.loads(config_path.read_text())
        if "policy_file" in config:
            policy_path = config_path.parent / config.pop("policy_file")
            config["policy"] = json.loads(policy_path.read_text())
        if config.get("model_revision", "UNSET") == "UNSET":
            raise ValueError("Pin model_revision before running")
        if "agents" in config:
            raise ValueError("Model runs use one endpoint/model per config, not deterministic agent lists")
        snapshots = load_snapshots(args.snapshots)
        rows = run_grid(snapshots, config, Path(args.output) / "records")
        write_json(Path(args.output) / "summary.json", summarize(rows))
        print(f"Saved {len(rows)} run records, including explicit N/A combinations.")
    elif args.command == "analyze":
        files = sorted(Path(args.records).glob("*.json"))
        rows = [json.loads(p.read_text()) for p in files]
        if not rows:
            raise ValueError("No records found")
        if len({r['run_id'] for r in rows}) != len(rows):
            raise ValueError("Duplicate run records")
        result = summarize(rows)
        if args.paired:
            result["paired"] = [{"agent": agent, "fault": fault, **paired_cluster_bootstrap(rows, agent, fault)}
                                for agent in sorted({r['agent'] for r in rows}) for fault in FAULTS]
            result["clean_cost_paired"] = [{"agent": agent, "endpoint": endpoint,
                **paired_cluster_bootstrap(rows, agent, "clean", endpoint=endpoint)}
                for agent in sorted({r['agent'] for r in rows})
                for endpoint in ("completion_success", "over_abstain")]
        write_json(args.output, result)
        print(f"Analyzed {len(rows)} records; saved {args.output}")


if __name__ == "__main__":
    main()
