"""Audit the bounded, explicitly authorized pilot using saved outputs only."""
from pathlib import Path
import collections
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chartguard.__main__ import load_snapshots
from chartguard.core import digest
from chartguard.original import original_verdict


def main():
    authorization = json.loads((ROOT / 'results/cloud-data-authorization.json').read_text())
    payload = ROOT / authorization['prepared_payload']
    snapshots = load_snapshots(payload)
    assert authorization['approved'] is True
    assert hashlib.sha256(payload.read_bytes()).hexdigest() == authorization['payload_sha256']
    assert digest(snapshots) == authorization['snapshot_digest']
    by_case = {s['case']['id']: s for s in snapshots}
    directory = ROOT / 'results/pilot-original-codex'
    all_rows = [json.loads(p.read_text()) for p in sorted((directory / 'records').glob('*.json'))]
    rows = [r for r in all_rows if r['status'] != 'not_applicable']
    expected = {(case, fault, arm) for case in by_case for fault in ('clean', 'unit_convert')
                for arm in ('baseline', 'evidence_prompt')}
    assert len(all_rows) == 8
    assert {(r['case_id'], r['fault'], r['arm']) for r in all_rows} == expected
    assert len(rows) == 6
    call_ids = []
    details = []
    for r in rows:
        snapshot = by_case[r['case_id']]
        assert r['identity']['snapshot_hash'] == digest(snapshot)
        assert r['restoration_verified'] is True
        assert (ROOT / 'results/source-versions' / (r['identity']['code_hash'] + '.zip')).exists()
        for usage in r['usage']:
            call_ids.append(usage['call_id'])
            events = [json.loads(line) for line in (directory / 'raw' / (usage['call_id'] + '.jsonl')).read_text().splitlines() if line.strip()]
            assert not any(e.get('item', {}).get('type') in
                           ('command_execution', 'mcp_tool_call', 'web_search', 'collab_tool_call') for e in events)
        clean_verdict = original_verdict(snapshot['case'], snapshot['resources'], r['messages'], r['answer']) if r['status'] == 'completed' else None
        details.append({key: r[key] for key in ('run_id', 'case_id', 'fault', 'arm', 'status', 'error', 'independent', 'original', 'citation_checks', 'answer')} |
                       {'original_on_clean_reference': clean_verdict, 'committed_writes': r['writes'],
                        'cli_turns': len(r['usage']), 'code_hash': r['identity']['code_hash']})
    assert len(call_ids) == len(set(call_ids))
    result = {
        'date': '2026-10-31', 'scope': 'Two previously prepared minimized benchmark cases; 47 observations',
        'payload_sha256': authorization['payload_sha256'], 'n_cases': len(snapshots),
        'n_episodes': len(rows), 'n_not_applicable': len(all_rows) - len(rows),
        'n_completed': sum(r['status'] == 'completed' for r in rows),
        'labels': dict(collections.Counter(r['independent']['label'] for r in rows)),
        'n_original_passes': sum(r['original']['pass'] is True for r in rows),
        'n_unsafe_among_original_passes': sum(r['original']['pass'] is True and r['independent']['unsafe_medication'] for r in rows),
        'cli_turns': len(call_ids),
        'usage': {key: sum(u.get(key, 0) for r in rows for u in r['usage']) for key in
                  ('prompt_tokens', 'completion_tokens', 'cached_input_tokens')},
        'all_restoration_checks_passed': True, 'codex_tool_execution_detected': False,
        'interpretation': 'Selected-case pilot only. No population rate, mitigation efficacy, or clinical harm estimate. Clean-reference re-scoring preserves raw model output without format normalization.',
        'episodes': details,
    }
    (directory / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'episodes'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
