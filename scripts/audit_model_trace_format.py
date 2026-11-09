"""Post-hoc route representation sensitivity; never overwrite raw verdicts."""
from pathlib import Path
import copy
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from chartguard.core import digest,inject
from chartguard.original import original_verdict
from chartguard.sandbox import ordered

if __name__=='__main__':
    snapshots={s['case']['id']:s for s in json.loads((ROOT/'data/snapshots-synthetic.json').read_text())}
    rows=[]
    for path in (ROOT/'results/pilot-codex/records').glob('*.json'):
        r=json.loads(path.read_text())
        if r['case_id']!='task5_synthetic0' or r['fault']!='unit_convert':continue
        s=snapshots[r['case_id']]
        baseline=ordered(s['resources']);observed,_=inject(s['case'],baseline,r['fault'])
        assert digest(observed)==r['observed_hash']
        messages=copy.deepcopy(r['messages']);changes=[]
        for m in messages:
            if m['role']!='assistant' or not m['content'].startswith('POST '):continue
            header,body=m['content'].split('\n',1);payload=json.loads(body)
            if payload.get('resourceType')!='MedicationRequest':continue
            for d in payload.get('dosageInstruction',[]):
                route=d.get('route')
                if isinstance(route,dict) and set(route)=={'text'}:
                    changes.append({'field':'dosageInstruction.route','before':route,'after':route['text']})
                    d['route']=route['text']
            m['content']=header+'\n'+json.dumps(payload)
        raw=original_verdict(s['case'],observed,r['messages'],r['answer'])
        normalized=original_verdict(s['case'],observed,messages,r['answer'])
        clean=original_verdict(s['case'],baseline,messages,r['answer'])
        assert raw['pass']==r['original']['pass']
        rows.append({'run_id':r['run_id'],'arm':r['arm'],'raw_original_pass':raw['pass'],
                     'route_normalized_corrupted_pass':normalized['pass'],'route_normalized_clean_pass':clean['pass'],
                     'changes':changes,'dose_changed':False,'raw_model_answer':r['answer'],
                     'normalized_grader_log':normalized['log']})
    assert len(rows)==2
    report={'evidence_type':'Post-hoc representation sensitivity, not raw original scores or additional model samples',
            'rule':'Replace only a single-key route object with its text string; leave doses, duration, codes, subject and outputs intact',
            'cases':rows}
    (ROOT/'results/model-trace-format-sensitivity.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
