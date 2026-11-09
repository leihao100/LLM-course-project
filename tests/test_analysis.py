import copy
import json
import tempfile
import unittest
from pathlib import Path

from chartguard.analysis import paired_cluster_bootstrap, summarize, wilson
from chartguard.core import inject
from chartguard.fixtures import synthetic_snapshots
from chartguard.runner import run_grid


def row(case="task5_1", patient="SYN-A", arm="baseline", unsafe=False, seed=0):
    return {"case_id": case, "patient_id": patient, "baseline_hash": "same", "seed": seed,
            "agent": "fixture", "arm": arm, "fault": "decimal_shift", "task_type": "task5",
            "status": "completed", "source_type": "synthetic_fixture",
            "original": {"pass": True, "error": None}, "mutation": {"changed": True}, "independent": {
                "unsafe_medication": unsafe, "label": "faithful_unsafe" if unsafe else "correct",
                "test_deviation": False, "observable_policy_violation": unsafe, "clean_requires_action": True}}


class StatisticsAndResumeTests(unittest.TestCase):
    def test_wilson_and_empty_denominator(self):
        self.assertIsNone(wilson(0, 0))
        lo, hi = wilson(0, 10)
        self.assertAlmostEqual(lo, 0)
        self.assertGreater(hi, 0)

    def test_paired_estimate_clusters_patients(self):
        rows = [row(unsafe=True), row(arm="evidence_prompt"),
                row(case="task9_2", patient="SYN-B", unsafe=True),
                row(case="task9_2", patient="SYN-B", arm="evidence_prompt")]
        result = paired_cluster_bootstrap(rows, "fixture", "decimal_shift", reps=100)
        self.assertEqual(result["estimate"], 1)
        self.assertEqual(result["ci95"], [1, 1])
        self.assertEqual(result["n_clusters"], 2)

    def test_missing_pair_is_error(self):
        with self.assertRaises(ValueError):
            paired_cluster_bootstrap([row()], "fixture", "decimal_shift")

    def test_duplicate_arm_is_error(self):
        with self.assertRaises(ValueError):
            paired_cluster_bootstrap([row(), row()], "fixture", "decimal_shift")

    def test_single_cluster_interval_is_not_overclaimed(self):
        result = paired_cluster_bootstrap([row(), row(arm="evidence_prompt")], "fixture", "decimal_shift", reps=30)
        self.assertIsNone(result["ci95"])

    def test_incomplete_runs_retained_in_denominator(self):
        a, b = row(unsafe=True), row(case="task5_2")
        b["status"] = "execution_error"
        b["independent"]["label"] = "invalid_run"
        group = summarize([a, b])["groups"][0]
        self.assertEqual(group["n_medication_runs"], 2)
        self.assertEqual(group["unsafe_rate_incomplete_bounds"], [0.5, 1])

    def test_resume_identity_and_policy_change(self):
        policy = json.loads((Path(__file__).resolve().parents[1] / "configs/policy.json").read_text())
        config = {"agents": ["chart_faithful_rule"], "arms": ["baseline"], "seeds": [0],
                  "faults": ["clean"], "policy": policy}
        with tempfile.TemporaryDirectory() as tmp:
            snapshots = synthetic_snapshots()[:1]
            a = run_grid(snapshots, config, tmp, deterministic=True)
            b = run_grid(snapshots, config, tmp, deterministic=True)
            self.assertEqual(a[0]["run_id"], b[0]["run_id"])
            changed = copy.deepcopy(config)
            changed["policy"]["version"] = "changed"
            c = run_grid(snapshots, changed, tmp, deterministic=True)
            self.assertNotEqual(a[0]["run_id"], c[0]["run_id"])
            self.assertEqual(len(list(Path(tmp).glob("*.json"))), 2)

    def test_unit_fault_checks_source_unit(self):
        snapshot = synthetic_snapshots()[0]
        for r in snapshot["resources"]:
            if r["resourceType"] == "Observation":
                r["valueQuantity"]["unit"] = "mmol/L"
        _, log = inject(snapshot["case"], snapshot["resources"], "unit_convert")
        self.assertFalse(log["applicable"])


if __name__ == "__main__":
    unittest.main()
