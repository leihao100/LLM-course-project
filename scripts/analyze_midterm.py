"""Reproducible midterm tables and fixed-trajectory policy sensitivity.

This script performs no inference and never normalizes model outputs.
"""
from pathlib import Path
import collections
import copy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chartguard.__main__ import load_snapshots
from chartguard.core import digest, inject, score
from chartguard.original import original_verdict


def main():
    datasets = [
        ('synthetic', 'pilot-codex', 'snapshots-inference-pilot.json'),
        ('original_legacy', 'pilot-original-codex', 'snapshots-cloud-minimized-pilot.json'),
        ('original_aligned', 'pilot-original-codex-aligned', 'snapshots-cloud-minimized-pilot.json'),
    ]
    summaries, sensitivity, audit = {}, [], []
    for name, directory, filename in datasets:
        snapshots = {s['case']['id']: s for s in load_snapshots(ROOT / 'data' / filename)}
        record_dir = ROOT / 'results' / directory
        all_rows = [json.loads(p.read_text()) for p in sorted((record_dir / 'records').glob('*.json'))]
        expected_count = 20 if name == 'synthetic' else 8
        assert len(all_rows) == expected_count, (name, len(all_rows))
        assert len({r['run_id'] for r in all_rows}) == len(all_rows)
        rows = [r for r in all_rows if r['status'] != 'not_applicable']
        summaries[name] = {
            'episodes': len(rows), 'unique_cases': len(snapshots),
            'completed': sum(r['status'] == 'completed' for r in rows),
            'labels': dict(collections.Counter(r['independent']['label'] for r in rows)),
            'original_passes': sum(r['original']['pass'] is True for r in rows),
            'unsafe': sum(r['independent']['unsafe_medication'] for r in rows),
            'unsafe_among_original_passes': sum(r['original']['pass'] is True and r['independent']['unsafe_medication'] for r in rows),
            'cli_turns': sum(len(r['usage']) for r in rows),
            'usage': {key: sum(u.get(key, 0) for r in rows for u in r['usage']) for key in
                      ('prompt_tokens', 'completion_tokens', 'cached_input_tokens')},
            'by_condition': {},
        }
        for fault in sorted({r['fault'] for r in rows}):
            subset = [r for r in rows if r['fault'] == fault]
            summaries[name]['by_condition'][fault] = {
                'episodes': len(subset), 'labels': dict(collections.Counter(r['independent']['label'] for r in subset)),
                'original_passes': sum(r['original']['pass'] is True for r in subset),
                'unsafe': sum(r['independent']['unsafe_medication'] for r in subset)}
        calls = []
        for r in rows:
            s = snapshots[r['case_id']]
            assert digest(s) == r['identity']['snapshot_hash']
            assert r['restoration_verified']
            observed, _ = inject(s['case'], s['resources'], r['fault'])
            assert digest(observed) == r['observed_hash']
            policy = copy.deepcopy(r['identity']['config']['policy'])
            base = score(s['case'], s['resources'], observed, r['writes'], r['answer'], r['explanation'], policy)
            if r['status'] == 'completed':
                assert base == r['independent'], r['run_id']
            policy['bounds'] = {}
            alternate = score(s['case'], s['resources'], observed, r['writes'], r['answer'], r['explanation'], policy)
            sensitivity.append({'dataset': name, 'run_id': r['run_id'], 'case_id': r['case_id'],
                                'fault': r['fault'], 'arm': r['arm'], 'status': r['status'],
                                'original_label': r['independent']['label'], 'no_bounds_label': alternate['label'],
                                'original_unsafe': r['independent']['unsafe_medication'],
                                'no_bounds_unsafe': alternate['unsafe_medication'],
                                'label_changed': r['independent']['label'] != alternate['label']})
            for u in r['usage']:
                calls.append(u['call_id'])
                events = [json.loads(line) for line in (record_dir / 'raw' / (u['call_id'] + '.jsonl')).read_text().splitlines() if line.strip()]
                assert not any(e.get('item', {}).get('type') in ('command_execution', 'mcp_tool_call', 'web_search', 'collab_tool_call') for e in events)
            if name == 'original_aligned':
                assert r['protocol_version'] == 'aligned-v1'
                clean_verdict = original_verdict(s['case'], s['resources'], r['messages'], r['answer']) if r['status'] == 'completed' else None
                audit.append({k: r[k] for k in ('run_id', 'case_id', 'fault', 'arm', 'status', 'original', 'independent', 'writes', 'answer', 'citation_checks')} |
                             {'original_on_clean_reference': clean_verdict, 'code_hash': r['identity']['code_hash']})
        assert len(calls) == len(set(calls))
        assert set(calls) == {p.stem for p in (record_dir / 'raw').glob('*.jsonl')}
    output = {'date': '2026-11-05', 'datasets': summaries, 'aligned_episodes': audit,
              'sensitivity': {'type': 'Fixed-trajectory re-scoring; not new model behavior under different instructions',
                              'episodes': len(sensitivity), 'changed_labels': sum(r['label_changed'] for r in sensitivity),
                              'changed_unsafe': sum(r['original_unsafe'] != r['no_bounds_unsafe'] for r in sensitivity),
                              'transitions': dict(collections.Counter(r['original_label'] + ' -> ' + r['no_bounds_label'] for r in sensitivity if r['label_changed'])),
                              'rows': sensitivity},
              'integrity': 'Exact snapshot and observed hashes verified; original labels replayed; no output normalization; all recorded tool calls and restorations checked.'}
    (ROOT / 'results/midterm-analysis.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    a = summaries['original_aligned']
    macros = {'AlignedN':a['episodes'], 'AlignedCompleted':a['completed'], 'AlignedPass':a['original_passes'],
              'AlignedUnsafe':a['unsafe'], 'AlignedUnsafePass':a['unsafe_among_original_passes'],
              'AlignedTurns':a['cli_turns'], 'SensitivityN':len(sensitivity),
              'SensitivityChanged':output['sensitivity']['changed_labels'],
              'SensitivityUnsafeChanged':output['sensitivity']['changed_unsafe']}
    (ROOT / 'paper/midterm/results_macros.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+str(v)+'}' for k,v in macros.items())+'\n')
    print(json.dumps({'datasets':summaries,'sensitivity':{k:v for k,v in output['sensitivity'].items() if k!='rows'}},indent=2))


if __name__ == '__main__':
    main()
