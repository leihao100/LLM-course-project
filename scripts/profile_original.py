"""Reproduce dataset profile and no-query/no-write original-grader control."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from chartguard.__main__ import load_snapshots
from chartguard.original import original_verdict
from chartguard.validation import preflight


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--snapshots',default='data/snapshots-real.json')
    parser.add_argument('--output',default='results/original-dataset-profile.json')
    args=parser.parse_args()
    snapshots=load_snapshots(args.snapshots)
    policy=json.loads((ROOT/'configs/policy.json').read_text())
    profile=preflight(snapshots,policy)
    controls=[]
    for s in snapshots:
        if s['case']['id'].split('_')[0] not in ('task5','task9'):continue
        verdict=original_verdict(s['case'],s['resources'],[{'role':'assistant','content':'FINISH([])'}],[])
        controls.append({'case_id':s['case']['id'],'original_pass':verdict['pass'],'error':verdict['error']})
    profile['no_query_no_write_control']={'n':len(controls),'passes':sum(r['original_pass'] is True for r in controls),
                                        'errors':sum(r['error'] is not None for r in controls),'cases':controls}
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(profile,indent=2)+'\n')
    print(json.dumps({k:v for k,v in profile.items() if k not in ['cases','no_query_no_write_control']}))
    print('No-query/no-write original-grader medication passes:',profile['no_query_no_write_control']['passes'],'/',len(controls))
