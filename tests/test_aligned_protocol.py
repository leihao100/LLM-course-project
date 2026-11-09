import json
import unittest
from chartguard.fixtures import synthetic_snapshots
from chartguard.original import ROOT
from chartguard.runner import run_episode, protocol_schemas, MITIGATION


class AlignedProtocolTests(unittest.TestCase):
    def test_schema_alignment_leaves_vendor_unchanged(self):
        before = (ROOT / 'vendor/funcs_v1.json').read_bytes()
        original = protocol_schemas('legacy')
        aligned = protocol_schemas('aligned-v1')
        for functions, expected in ((original, 'object'), (aligned, 'string')):
            med = next(f for f in functions if f['name'] == 'POST {api_base}/MedicationRequest')
            self.assertEqual(med['parameters']['properties']['dosageInstruction']['items']['properties']['route']['type'], expected)
        self.assertEqual(before, (ROOT / 'vendor/funcs_v1.json').read_bytes())
        with self.assertRaises(ValueError):
            protocol_schemas('unknown')

    def test_shared_format_rules_and_unchanged_dose_reference(self):
        snapshot = next(s for s in synthetic_snapshots() if s['case']['id'] == 'task5_synthetic0')
        policy = json.loads((ROOT / 'configs/policy.json').read_text())
        rows = [run_episode(snapshot, 'unit_convert', 'chart_rule', policy, arm=arm,
                            protocol_version='aligned-v1') for arm in ('baseline', 'evidence_prompt')]
        self.assertEqual(rows[1]['messages'][0]['content'], rows[0]['messages'][0]['content'] + MITIGATION)
        for row in rows:
            self.assertTrue(row['original']['pass'])
            self.assertEqual(row['independent']['label'], 'faithful_unsafe')
            self.assertTrue(row['restoration_verified'])


if __name__ == '__main__':
    unittest.main()
