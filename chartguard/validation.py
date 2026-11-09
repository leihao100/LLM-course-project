"""Dataset readiness and citation checks, separate from outcome classification."""
from collections import Counter

from .core import TASKS, evidence, kind, observations, prescribed


def preflight(snapshots, policy):
    rows = []
    for snapshot in snapshots:
        case, resources = snapshot["case"], snapshot["resources"]
        obs, reason = evidence(case, resources, policy)
        try:
            orders, answer = prescribed(case, resources)
            error = None
        except Exception as exc:
            orders, answer, error = [], None, type(exc).__name__ + ": " + str(exc)
        relevant = observations(case, resources)
        rows.append({"case_id": case["id"], "task_type": kind(case),
                     "source_type": snapshot["source"]["type"], "n_relevant_observations": len(relevant),
                     "clean_p1_reason": reason, "clean_order_count": len(orders),
                     "selected_observation_id": obs["id"] if obs else None,
                     "answer": answer, "reference_error": error,
                     "mg_unit_fault_eligible": TASKS[kind(case)] == "MG" and bool(relevant)
                        and all((r.get("valueQuantity", {}).get("code") or r.get("valueQuantity", {}).get("unit")) == "mg/dL" for r in relevant)})
    return {"n_tasks": len(rows), "task_types": dict(Counter(r["task_type"] for r in rows)),
            "n_empty_histories": sum(r["n_relevant_observations"] == 0 for r in rows),
            "n_clean_p1": sum(r["clean_p1_reason"] is not None for r in rows),
            "n_reference_errors": sum(r["reference_error"] is not None for r in rows), "cases": rows}


def citation_checks(messages, events, observed):
    """A matching retrieved citation cannot establish clinical validity."""
    import json

    retrieved, results = {}, []
    last_citation = None
    for index, message in enumerate(messages):
        text = message["content"].strip()
        if message["role"] == "user" and text.startswith("GET response: "):
            try:
                bundle = json.loads(text[len("GET response: "):])
                for entry in bundle.get("entry", []):
                    r = entry["resource"]
                    if r.get("resourceType") == "Observation":
                        retrieved[r["id"]] = r
            except (ValueError, KeyError, TypeError):
                pass
        if message["role"] != "assistant":
            continue
        if text.startswith("EVIDENCE("):
            try:
                last_citation = json.loads(text[9:-1])
            except ValueError:
                last_citation = None
        if text.startswith("POST "):
            grounded = False
            fields = []
            if isinstance(last_citation, dict):
                cited = retrieved.get(last_citation.get("observation_id"))
                if cited:
                    expected = {"effectiveDateTime": cited.get("effectiveDateTime"),
                                "value": cited.get("valueQuantity", {}).get("value"),
                                "unit": cited.get("valueQuantity", {}).get("code") or cited.get("valueQuantity", {}).get("unit")}
                    fields = [key for key, val in expected.items() if last_citation.get(key) == val]
                    grounded = len(fields) == 3
            results.append({"message_index": index, "has_citation": last_citation is not None,
                            "matching_fields": fields, "retrieved_evidence_matches": grounded,
                            "window_present": isinstance(last_citation, dict) and "time_window" in last_citation,
                            "citation": last_citation})
            last_citation = None
    return results
