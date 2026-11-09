import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from chartguard.clients import CodexCliClient
from chartguard.core import digest
from chartguard.runner import check_benchmark_cloud_authorization


class CodexSubscriptionTests(unittest.TestCase):
    def client(self,tmp):
        return CodexCliClient({"working_directory":tmp,"raw_directory":str(Path(tmp)/"raw")})

    def test_subscription_output_and_usage(self):
        events=[{"type":"item.completed","item":{"type":"agent_message","text":"FINISH([])"}},
                {"type":"turn.completed","usage":{"input_tokens":20,"output_tokens":4}}]
        status=subprocess.CompletedProcess([],0,"","Logged in using ChatGPT")
        inference=subprocess.CompletedProcess([],0,"\n".join(json.dumps(e) for e in events),"")
        with tempfile.TemporaryDirectory() as tmp, patch("shutil.which",return_value="/bin/codex"), patch("subprocess.run",side_effect=[status,inference]) as call:
            text,usage=self.client(tmp).next([{"role":"user","content":"fixture"}],0)
            self.assertEqual(text,"FINISH([])")
            self.assertEqual(usage["prompt_tokens"],20)
            self.assertNotIn("OPENAI_API_KEY",call.call_args.kwargs["env"])
            self.assertNotIn("CODEX_API_KEY",call.call_args.kwargs["env"])
            self.assertTrue(list((Path(tmp)/"raw").glob("*.jsonl")))

    def test_api_key_login_rejected(self):
        status=subprocess.CompletedProcess([],0,"","Logged in using an API key")
        with tempfile.TemporaryDirectory() as tmp, patch("shutil.which",return_value="/bin/codex"), patch("subprocess.run",return_value=status):
            with self.assertRaises(RuntimeError):self.client(tmp)

    def test_tool_use_invalidates_model_only_trial(self):
        status=subprocess.CompletedProcess([],0,"","Logged in using ChatGPT")
        events=[{"type":"item.completed","item":{"type":"command_execution","command":"ls"}}]
        inference=subprocess.CompletedProcess([],0,"\n".join(json.dumps(e) for e in events),"")
        with tempfile.TemporaryDirectory() as tmp, patch("shutil.which",return_value="/bin/codex"), patch("subprocess.run",side_effect=[status,inference]):
            with self.assertRaises(RuntimeError):self.client(tmp).next([],0)

    def test_original_cloud_requires_exact_authorized_snapshot(self):
        snapshots=[{'source':{'type':'benchmark_snapshot'},'case':{'id':'task5_fixture'},'resources':[]}]
        with self.assertRaises(ValueError):
            check_benchmark_cloud_authorization(snapshots,{'backend':'codex_cli'})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'consent.json';config={'backend':'codex_cli','cloud_authorization_file':str(path)}
            path.write_text(json.dumps({'approved':False,'snapshot_digest':digest(snapshots)}))
            with self.assertRaises(ValueError):check_benchmark_cloud_authorization(snapshots,config)
            path.write_text(json.dumps({'approved':True,'snapshot_digest':digest(snapshots)}))
            check_benchmark_cloud_authorization(snapshots,config)
            snapshots[0]['resources']=[{'changed':True}]
            with self.assertRaises(ValueError):check_benchmark_cloud_authorization(snapshots,config)
