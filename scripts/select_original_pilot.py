"""Select the first action-required Mg and K tasks, before model inference.

Read only relevant complete histories; query counts are bounded by the original
scorer's 5,000-record limit. Follow server pagination rather than assuming a page
is the full history. Never mutate the source FHIR service.
"""
import json
import hashlib
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlencode, urljoin, urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from chartguard.core import NOW,evidence,kind,prescribed
from chartguard.sandbox import ordered


def search(base, resource_type, params):
    url=base+resource_type+'?'+urlencode(params)
    rows=[]
    seen=set()
    while url:
        if url in seen:raise ValueError('Pagination cycle')
        if urlparse(url).netloc!=urlparse(base).netloc:raise ValueError('Cross-origin next link')
        seen.add(url)
        req=urllib.request.Request(url,headers={'Accept':'application/fhir+json'})
        with urllib.request.urlopen(req,timeout=90) as response:data=json.load(response)
        if data.get('resourceType')!='Bundle':raise ValueError('Expected Bundle')
        rows.extend(e['resource'] for e in data.get('entry',[]))
        links=[link['url'] for link in data.get('link',[]) if link.get('relation')=='next']
        url=urljoin(url,links[0]) if links else None
    return rows


if __name__=='__main__':
    base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:18080/fhir/'
    tasks=json.loads((ROOT/'vendor/tasks_original.json').read_text())
    policy=json.loads((ROOT/'configs/policy.json').read_text())
    selected=[]
    screening=[]
    for task_type,code in [('task5','MG'),('task9','K')]:
        for case in [c for c in tasks if kind(c)==task_type]:
            resources=search(base,'Observation',{'patient':case['eval_MRN'],'code':code,'_count':500})
            obs,reason=evidence(case,resources,policy)
            orders,answer=prescribed(case,resources)
            row={'case_id':case['id'],'n_observations':len(resources),'p1_reason':reason,
                 'clean_requires_action':bool(orders),'answer':answer}
            screening.append(row)
            print(json.dumps(row),flush=True)
            if reason is None and orders:
                patients=search(base,'Patient',{'identifier':case['eval_MRN']})
                selected.append({'case':case,'resources':ordered(resources+patients),
                                 'source':{'type':'benchmark_snapshot','provenance':
                                     'MedAgentBench commit 99260117137b09f04837a8c18d18a1107efa55ae; '+
                                     'jyxsu6/medagentbench@sha256:3fb83d7ed71c5476f9eb6212bd440a909ef7505922bbc757dc488a8fc0701966',
                                     'selection':'first action-required case in original category order, before inference'}})
                break
    if len(selected)!=2:raise RuntimeError('Did not find one eligible case per category; inspect screening log')
    output=ROOT/'data/snapshots-original-pilot.json'
    raw=json.dumps(selected,ensure_ascii=False,indent=2).encode()
    output.write_bytes(raw)
    output.with_suffix('.json.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n')
    (ROOT/'results/original-pilot-screening.json').write_text(json.dumps(screening,indent=2)+'\n')
    print('Selected:',[s['case']['id'] for s in selected],flush=True)
