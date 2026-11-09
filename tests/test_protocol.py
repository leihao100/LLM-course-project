import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chartguard.__main__ import load_snapshots
from chartguard.fixtures import observation
from chartguard.runner import ChatClient
from chartguard.sandbox import export_snapshots
from chartguard.validation import citation_checks


class ProtocolAdapterTests(unittest.TestCase):
    def test_chat_http_payload_and_usage(self):
        config = {"base_url": "http://localhost:8000/v1", "model": "fixture"}
        def respond(req, timeout):
            body = json.loads(req.data)
            self.assertEqual(body["model"], "fixture")
            self.assertEqual(body["temperature"], 0)
            self.assertEqual(body["seed"], 7)
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": "FINISH([])"}}],
                                         "usage": {"completion_tokens": 4}}).encode())
        with patch("urllib.request.urlopen", side_effect=respond):
            text, usage = ChatClient(config).next([{"role": "user", "content": "test"}], 7)
        self.assertEqual(text, "FINISH([])")
        self.assertEqual(usage["completion_tokens"], 4)

    def test_export_pagination_and_checksum(self):
        case = {"id": "task5_fixture", "eval_MRN": "SYN-TEST"}
        obs = observation("SYN-TEST", "MG", 1.8)
        responses = [
            {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient", "id": "SYN-TEST"}}]},
            {"resourceType": "Bundle", "entry": [{"resource": obs}],
             "link": [{"relation": "next", "url": "http://localhost/fhir/Observation?page=2"}]},
            {"resourceType": "Bundle", "entry": []}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.json"
            with patch("urllib.request.urlopen", side_effect=[io.BytesIO(json.dumps(r).encode()) for r in responses]):
                self.assertEqual(export_snapshots("http://localhost/fhir", [case], path, "fixture"), 1)
            snapshots = load_snapshots(path)
            self.assertEqual(len(snapshots[0]["resources"]), 2)
            path.write_text("[]")
            with self.assertRaises(ValueError):
                load_snapshots(path)

    def test_export_rejects_cross_origin_pagination(self):
        responses = [{"resourceType": "Bundle"},
                     {"resourceType": "Bundle", "link": [{"relation": "next", "url": "http://elsewhere/next"}]}]
        with tempfile.TemporaryDirectory() as tmp:
            with patch("urllib.request.urlopen", side_effect=[io.BytesIO(json.dumps(r).encode()) for r in responses]):
                with self.assertRaises(ValueError):
                    export_snapshots("http://localhost/fhir", [{"id": "task5_1", "eval_MRN": "SYN-A"}], Path(tmp)/"s.json", "test")

    def test_citation_must_match_previously_retrieved_evidence(self):
        obs = observation("SYN-A", "MG", 1.8)
        cite = {"observation_id": obs["id"], "effectiveDateTime": obs["effectiveDateTime"],
                "value": 1.8, "unit": "mg/dL", "time_window": "24 hours"}
        messages = [{"role": "user", "content": "GET response: " + json.dumps({"entry": [{"resource": obs}]})},
                    {"role": "assistant", "content": "EVIDENCE(" + json.dumps(cite) + ")"},
                    {"role": "assistant", "content": "POST http://sandbox.local/fhir/MedicationRequest\n{}"}]
        self.assertTrue(citation_checks(messages, [], [obs])[0]["retrieved_evidence_matches"])
        self.assertFalse(citation_checks(messages[1:], [], [obs])[0]["retrieved_evidence_matches"])


if __name__ == "__main__":
    unittest.main()
