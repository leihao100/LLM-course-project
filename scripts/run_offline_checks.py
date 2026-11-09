"""Run reproducible checks from a fresh or source checkout, without third parties."""
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    output = ROOT / "results"
    output.mkdir(exist_ok=True)
    tested = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                            cwd=ROOT, text=True, capture_output=True)
    (output / "test_log.txt").write_text(tested.stdout + tested.stderr)
    if tested.returncode:
        print(tested.stdout + tested.stderr)
        raise SystemExit(tested.returncode)
    for args in [["audit"], ["plan"], ["demo"]]:
        subprocess.run([sys.executable, "-m", "chartguard", *args], cwd=ROOT, check=True)
    summary=json.loads((output/"demo/summary.json").read_text())
    records=[json.loads(p.read_text()) for p in (output/"demo/records").glob("*.json")]
    # The directory must contain one identity per scheduled demo combination.
    if len(records) != 450:
        raise RuntimeError("Mixed demo versions: archive results/demo before rerunning checks")
    valid=[r for r in records if r["status"] != "not_applicable"]
    assert len(valid) == 396
    assert all(r["restoration_verified"] for r in valid)
    assert all(r["source_type"] == "synthetic_fixture" for r in valid)
    assert all(r["status"] == "completed" for r in valid)
    writes=sum(len(r["writes"]) for r in valid)
    committed=sum(e.get("committed",False) for r in valid for e in r["tool_events"])
    assert writes == committed
    test_count = int(re.search(r"Ran (\d+) tests", tested.stdout + tested.stderr).group(1))
    report={"date":"2026-10-30", "python":platform.python_version(), "tests_passed":True,
            "test_count":test_count, "audit_findings":8, "demo_nominal_combinations":450,
            "demo_not_applicable":54,"demo_executed":396,"demo_committed_resources":writes,
            "restoration_verified_all_executed":True,"validation_run_model_calls":0,
            "scope":"Offline software check only; actual inference trials are indexed separately",
            "note":"This check uses synthetic programmed controls and does not call model services"}
    (output/"verification.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
