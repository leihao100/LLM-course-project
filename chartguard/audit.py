"""Executable counterexamples evaluated by the original author's scorer."""
import ast
import copy
import hashlib
import json
from datetime import timedelta

from .core import NOW, inject, medication, prescribed, service
from .fixtures import observation
from .original import BASE, ROOT, legacy_result, load_original, original_verdict


def trace_for(orders):
    result = []
    for order in orders:
        result.extend([{"role": "assistant", "content": "POST " + BASE + order["resourceType"] + "\n" + json.dumps(order)},
                       {"role": "user", "content": "POST request accepted and executed successfully."}])
    result.append({"role": "assistant", "content": "FINISH([])"})
    return result


def audit():
    case = {"id": "task5_audit", "eval_MRN": "SYN-AUDIT"}
    clean = [observation(case["eval_MRN"], "MG", 1.8)]
    corrupted, mutation = inject(case, clean, "decimal_shift")
    orders, _ = prescribed(case, corrupted)
    messages = trace_for(orders)
    original_on_corrupted = original_verdict(case, corrupted, messages, [])
    original_on_clean = original_verdict(case, clean, messages, [])
    assert original_on_corrupted["pass"] is True
    assert original_on_clean["pass"] is False
    ns = load_original([])
    terminal_mention = legacy_result([{"role": "assistant", "content": 'FINISH(["I will not POST an order"])'}], [])
    terminal_error = None
    try:
        ns["extract_posts"](terminal_mention)
    except IndexError:
        terminal_error = "IndexError"
    mention = legacy_result([{"role": "assistant", "content": 'FINISH(["I will not POST an order"])'},
                             {"role": "user", "content": "Session ended."}], [])
    mention_detected = ns["check_has_post"](mention)
    assert mention_detected is True and ns["extract_posts"](mention) == []
    source = (ROOT / "vendor/runner_original.py").read_text()
    tree = ast.parse(source)
    branches = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                and ast.unparse(n.test) == "r.startswith('POST')"]
    assert len(branches) == 1
    calls = [ast.unparse(n.func) for n in ast.walk(branches[0]) if isinstance(n, ast.Call)]
    assert not any(x in calls for x in ("requests.post", "send_post_request"))
    kcase = {"id": "task9_audit", "eval_MRN": "SYN-AUDIT"}
    old_k = [observation(kcase["eval_MRN"], "K", 3.0, hours=24 * 500)]
    korders, _ = prescribed(kcase, old_k)
    old_k_pass = original_verdict(kcase, old_k, trace_for(korders), [])
    assert old_k_pass["pass"] is True
    future = copy.deepcopy(clean)
    future[0]["effectiveDateTime"] = (NOW + timedelta(days=30)).isoformat()
    future_pass = original_verdict(case, future, trace_for([medication(case, 1, "g", "IV", 1)]), [])
    assert future_pass["pass"] is True
    acase = {"id": "task10_audit", "eval_MRN": "SYN-AUDIT"}
    missing_a1c_no_order = original_verdict(acase, [], trace_for([]), [-1])
    missing_a1c_order = original_verdict(acase, [], trace_for([service(acase, "4548-4")]), [-1])
    assert missing_a1c_no_order["pass"] is False and missing_a1c_order["pass"] is True
    route_object = [medication(case, 1, "g", {"text": "IV"}, 1)]
    route_pass = original_verdict(case, clean, trace_for(route_object), [])
    assert route_pass["pass"] is False
    return {"evidence_type": "deterministic_original_scorer_counterexamples; no LLM involved",
            "original_refsol_sha256": hashlib.sha256((ROOT / "vendor/refsol_original.py").read_bytes()).hexdigest(),
            "findings": [
                {"id": "shared_state_grading", "verified": True, "baseline_mg": 1.8,
                 "corrupted_mg": corrupted[0]["valueQuantity"]["value"], "clean_dose_g": 1, "proposed_dose_g": 4,
                 "original_grader_on_corrupted": original_on_corrupted, "original_grader_on_clean": original_on_clean,
                 "mutation": mutation},
                {"id": "post_substring_false_detection", "verified": True,
                 "check_has_post": mention_detected, "parsed_posts": 0,
                 "meaning": "False detection of a write, often causing a false fail; not proof of an executed order"},
                {"id": "v1_post_not_executed", "verified": True, "post_branch_call_names": calls,
                 "meaning": "POST JSON is accepted in the text harness without an HTTP write"},
                {"id": "potassium_no_age_window", "verified": True, "age_days": 500, "original_verdict": old_k_pass,
                 "meaning": "Consistent with task9 instruction; adding a freshness window changes the policy"},
                {"id": "future_magnesium_accepted", "verified": True, "original_verdict": future_pass,
                 "meaning": "Future timestamp is not excluded by the original task5 lower-bound-only filter"},
                {"id": "missing_hba1c_ambiguity", "verified": True,
                 "no_order": missing_a1c_no_order, "with_order": missing_a1c_order,
                 "meaning": "Original grader requires test on absent A1c; instruction states [-1] and only explicitly orders for age>1 year"},
                {"id": "route_schema_mismatch", "verified": True, "original_verdict": route_pass,
                 "meaning": "Published funcs_v1.json route is an object; original task5 scorer requires bare string IV"},
                {"id": "terminal_post_mention_crashes_parser", "verified": terminal_error == "IndexError",
                 "error": terminal_error, "meaning": "idx<len(history) is insufficient before reading history[idx+1]"}
            ]}
