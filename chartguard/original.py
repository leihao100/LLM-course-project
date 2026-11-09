"""Execute the downloaded, unmodified original scorer on a frozen snapshot.

Only its relative utils import is removed. Its network GET helper is replaced by
a fixture reader returning the text representation expected by refsol.py.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from .core import code_of, subject_of

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "vendor/refsol_original.py").exists():
    ROOT = Path(sys.prefix) / "share/clinical-chart-safety"
BASE = "http://sandbox.local/fhir/"


def load_original(resources):
    if not __debug__:
        raise RuntimeError("Do not run with python -O: the original grader uses assert checks")
    source = (ROOT / "vendor/refsol_original.py").read_text()
    tree = ast.parse(source)
    tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and n.level)]

    def get(url, *args, **kwargs):
        parsed = urlparse(url)
        q = parse_qs(parsed.query)
        rt = parsed.path.rstrip("/").split("/")[-1]
        result = [r for r in resources if r["resourceType"] == rt]
        if "patient" in q:
            result = [r for r in result if subject_of(r) == q["patient"][0]]
        if "code" in q:
            result = [r for r in result if code_of(r) == q["code"][0]]
        return {"status_code": 200, "data": json.dumps({"entry": [{"resource": r} for r in result]})}

    namespace = {"send_get_request": get}
    exec(compile(tree, "refsol_original.py", "exec"), namespace)
    return namespace


def legacy_result(messages, answer):
    return SimpleNamespace(history=[SimpleNamespace(role="agent" if m["role"] == "assistant" else "user",
                                                    content=m["content"]) for m in messages],
                           result=json.dumps(answer))


def original_verdict(case, resources, messages, answer):
    namespace = load_original(resources)
    stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(stream):
            value = namespace[case["id"].split("_")[0]](case, legacy_result(messages, answer), BASE)
        return {"pass": value is True, "error": None, "log": stream.getvalue()}
    except Exception as exc:
        # A grader exception is not silently converted to an ordinary fail.
        return {"pass": None, "error": type(exc).__name__ + ": " + str(exc), "log": stream.getvalue()}
