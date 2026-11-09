"""An isolated JSON resource sandbox backed by SQLite, not a full FHIR server."""
from __future__ import annotations

import copy
import json
import sqlite3
import uuid
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .core import TASKS, canonical, code_of, kind, subject_of


def ordered(resources):
    return sorted(copy.deepcopy(resources), key=lambda r: (r["resourceType"], r["id"]))


class Sandbox:
    def __init__(self, resources, patient, path=":memory:"):
        self.patient = patient
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE resources (kind TEXT,id TEXT,body TEXT,PRIMARY KEY(kind,id))")
        self.events = []
        for r in ordered(resources):
            self.db.execute("INSERT INTO resources VALUES (?,?,?)", (r["resourceType"], r["id"], canonical(r)))
        self.db.commit()

    def all(self):
        return [json.loads(x[0]) for x in self.db.execute("SELECT body FROM resources ORDER BY kind,id")]

    def close(self):
        self.db.close()

    def search(self, url):
        parsed = urlparse(url)
        # The model cannot request external URLs; GET is evaluated locally.
        if parsed.scheme not in ("", "http") or parsed.netloc not in ("", "sandbox.local"):
            raise ValueError("Only http://sandbox.local/fhir/ is allowed")
        rt = parsed.path.rstrip("/").split("/")[-1]
        if rt not in ("Observation", "Patient", "MedicationRequest", "ServiceRequest"):
            raise ValueError("Unsupported resource type")
        q = parse_qs(parsed.query)
        requested_patient = q.get("patient", q.get("identifier", [self.patient]))[0]
        if requested_patient != self.patient:
            raise ValueError("Cross-patient query")
        resources = [r for r in self.all() if r["resourceType"] == rt]
        if rt != "Patient":
            resources = [r for r in resources if subject_of(r) == self.patient]
        if "code" in q:
            resources = [r for r in resources if code_of(r) == q["code"][0]]
        unsupported = set(q) - {"patient", "identifier", "code", "_format", "_count", "_sort", "_offset"}
        if unsupported:
            raise ValueError(f"Unsupported search parameter(s): {sorted(unsupported)}; query full history")
        if "_sort" in q:
            sort = q["_sort"][0]
            if rt != "Observation" or sort not in ("date", "-date"):
                raise ValueError("Only Observation _sort=date or -date is supported")
            from .core import timestamp
            resources = sorted(resources, key=lambda r: (timestamp(r), r["id"]), reverse=sort.startswith("-"))
        count, offset = int(q.get("_count", ["100"])[0]), int(q.get("_offset", ["0"])[0])
        if not 1 <= count <= 5000 or offset < 0:
            raise ValueError("_count must be 1..5000 and _offset nonnegative")
        total = len(resources)
        page = resources[offset:offset+count]
        bundle = {"resourceType": "Bundle", "type": "searchset", "total": total,
                  "entry": [{"resource": r} for r in page]}
        if offset+count < total:
            next_query = dict(q)
            next_query["_offset"] = [str(offset+count)]
            next_url = urlunparse(parsed._replace(query=urlencode(next_query, doseq=True)))
            bundle["link"] = [{"relation": "next", "url": next_url}]
        self.events.append({"method": "GET", "url": url, "status": 200, "response": bundle})
        return bundle

    def write(self, url, payload):
        parsed = urlparse(url)
        if parsed.scheme not in ("", "http") or parsed.netloc not in ("", "sandbox.local"):
            raise ValueError("External write URL")
        rt = parsed.path.rstrip("/").split("/")[-1]
        event = {"method": "POST", "url": url, "payload": copy.deepcopy(payload), "status": 400, "committed": False}
        self.events.append(event)
        if rt not in ("MedicationRequest", "ServiceRequest") or payload.get("resourceType") != rt:
            raise ValueError("Invalid write type")
        if subject_of(payload) != self.patient:
            raise ValueError("Cross-patient write")
        if payload.get("status") != "active" or payload.get("intent") != "order":
            raise ValueError("Invalid order status/intent")
        # Semantic errors remain committed and are graded as unsafe. This is a
        # research order store, not a clinical validation or dose-checking service.
        saved = copy.deepcopy(payload)
        saved["id"] = "write-" + uuid.uuid4().hex
        self.db.execute("INSERT INTO resources VALUES (?,?,?)", (rt, saved["id"], canonical(saved)))
        self.db.commit()
        readback = json.loads(self.db.execute("SELECT body FROM resources WHERE kind=? AND id=?",
                                              (rt, saved["id"])).fetchone()[0])
        assert readback == saved
        event.update(status=201, committed=True, resource_id=saved["id"], readback=readback)
        return readback

    def writes(self):
        return [copy.deepcopy(e["readback"]) for e in self.events if e.get("committed")]


def export_snapshots(base_url, cases, output, provenance):
    """Read-only adapter for an already running benchmark FHIR endpoint.

    Follow every Bundle next link, constrain links to the endpoint origin, and
    retain full Observation histories for post-fault fallback selection.
    """
    import hashlib
    import pathlib
    import urllib.request
    from urllib.parse import urlencode, urljoin

    base_url = base_url.rstrip("/") + "/"
    origin = urlparse(base_url)
    exported = []
    for case in cases:
        resources = []
        for rt, params in (("Patient", {"identifier": case["eval_MRN"]}),
                           ("Observation", {"patient": case["eval_MRN"], "code": TASKS[kind(case)], "_count": "500"})):
            next_url = base_url + rt + "?" + urlencode(params)
            seen = set()
            while next_url:
                parsed = urlparse(next_url)
                if (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc):
                    raise ValueError("Cross-origin pagination link")
                if next_url in seen:
                    raise ValueError("Pagination cycle")
                seen.add(next_url)
                req = urllib.request.Request(next_url, headers={"Accept": "application/fhir+json"})
                # Authorization may be supplied only via an environment variable.
                import os
                token = os.environ.get("FHIR_BEARER_TOKEN")
                if token:
                    req.add_header("Authorization", "Bearer " + token)
                with urllib.request.urlopen(req, timeout=60) as response:
                    bundle = json.load(response)
                if bundle.get("resourceType") != "Bundle":
                    raise ValueError("Expected a FHIR search Bundle")
                resources.extend(e["resource"] for e in bundle.get("entry", []))
                links = [l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"]
                next_url = urljoin(next_url, links[0]) if links else None
        unique = {(r["resourceType"], r["id"]): r for r in resources}
        exported.append({"case": case, "resources": ordered(list(unique.values())),
                         "source": {"type": "benchmark_snapshot", "provenance": provenance}})
    path = pathlib.Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(exported, ensure_ascii=False, indent=2).encode()
    path.write_bytes(raw)
    path.with_suffix(path.suffix + ".sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")
    return len(exported)
