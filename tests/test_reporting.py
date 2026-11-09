import unittest
from chartguard.analysis import paired_cluster_bootstrap
from test_analysis import row


class CleanCostTests(unittest.TestCase):
    def test_clean_completion_loss(self):
        a, b = row(), row(arm="evidence_prompt")
        a["fault"] = b["fault"] = "clean"
        b["independent"]["label"] = "over_abstain"
        result = paired_cluster_bootstrap([a, b], "fixture", "clean", reps=30, endpoint="completion_success")
        self.assertEqual(result["estimate"], 1)

    def test_over_abstention_delta(self):
        a, b = row(), row(arm="evidence_prompt")
        a["fault"] = b["fault"] = "clean"
        b["independent"]["label"] = "over_abstain"
        result = paired_cluster_bootstrap([a, b], "fixture", "clean", reps=30, endpoint="over_abstain")
        self.assertEqual(result["estimate"], -1)


if __name__ == "__main__":
    unittest.main()
