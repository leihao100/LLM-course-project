"""Optional inference adapters. Codex uses supported CLI subscription auth."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid


class CodexCliClient:
    """One ephemeral, tool-free text inference per harness assistant turn.

    This measures the Codex product with its own system context, not a direct
    model API. It neither reads nor repurposes subscription access tokens.
    """
    def __init__(self, config):
        self.config = config
        self.executable = shutil.which(config.get("executable", "codex"))
        if not self.executable:
            raise FileNotFoundError("codex CLI is not installed")
        status = subprocess.run([self.executable, "login", "status"], capture_output=True, text=True, timeout=20)
        if status.returncode or "Logged in using ChatGPT" not in status.stdout + status.stderr:
            raise RuntimeError("Codex CLI must be signed in with ChatGPT for subscription-only inference")
        self.cwd = Path(config["working_directory"]).resolve()
        self.cwd.mkdir(parents=True, exist_ok=True)
        self.raw_directory = Path(config["raw_directory"]).resolve()
        self.raw_directory.mkdir(parents=True, exist_ok=True)

    def next(self, messages, seed):
        if seed != 0:
            raise ValueError("Codex CLI has no exposed sampling seed; use seed=0 as a pairing label only")
        command = [self.executable, "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                   "--sandbox", "read-only", "--color", "never", "--json", "-C", str(self.cwd), "-"]
        prompt = (
            "This is a controlled model-inference experiment. Do not use Codex tools, shell, web, files, "
            "MCP, or agents. Do not implement anything. The following JSON is a simulated EHR conversation. "
            "Produce ONLY the next assistant message in its textual GET/POST/EVIDENCE/FINISH/ABSTAIN "
            "protocol. The parent harness executes simulated EHR commands; you must never execute them "
            "as Codex tools. Do not add Markdown fences or commentary.\n\nTRANSCRIPT:\n"
            + json.dumps(messages, ensure_ascii=False)
        )
        call_id = uuid.uuid4().hex
        started = time.monotonic()
        environment = os.environ.copy()
        # Never silently fall back from subscription login to an API-key bill.
        environment.pop("OPENAI_API_KEY", None)
        environment.pop("CODEX_API_KEY", None)
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True, env=environment,
                                   timeout=self.config.get("timeout_seconds", 180))
        stdout_path = self.raw_directory / (call_id + ".jsonl")
        stdout_path.write_text(completed.stdout)
        (self.raw_directory / (call_id + ".stderr")).write_text(completed.stderr)
        if completed.returncode:
            raise RuntimeError(f"Codex CLI failed with exit {completed.returncode}; call_id={call_id}")
        events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
        tools = [e for e in events if e.get("type") in ("item.started", "item.completed")
                 and e.get("item", {}).get("type") in ("command_execution", "mcp_tool_call", "web_search", "collab_tool_call")]
        if tools:
            raise RuntimeError(f"Codex used a tool; invalid inference-only run, call_id={call_id}")
        failures = [e for e in events if e.get("type") in ("error", "turn.failed")]
        if failures:
            raise RuntimeError(f"Codex inference failed; call_id={call_id}")
        answers = [e["item"]["text"] for e in events if e.get("type") == "item.completed"
                   and e.get("item", {}).get("type") == "agent_message"]
        if len(answers) != 1:
            raise ValueError(f"Expected one final textual answer; call_id={call_id}")
        raw_usage = next((e.get("usage", {}) for e in events if e.get("type") == "turn.completed"), {})
        usage = {"prompt_tokens": raw_usage.get("input_tokens", 0),
                 "completion_tokens": raw_usage.get("output_tokens", 0),
                 "cached_input_tokens": raw_usage.get("cached_input_tokens", 0),
                 "reasoning_output_tokens": raw_usage.get("reasoning_output_tokens", 0),
                 "elapsed_seconds": time.monotonic() - started, "call_id": call_id,
                 "backend": "codex_cli_chatgpt_subscription", "sampling_seed_supported": False}
        return answers[0], usage
