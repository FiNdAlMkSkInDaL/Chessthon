"""Audit all eight frozen runs before comparing Linux search throughput."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((HERE/'plan.json').read_text())
data={}; metadata=[]; compared=0
for lane in plan['lanes']:
    for variant in plan['variants']:
        path=HERE/f'{variant}-{lane}.jsonl'
        rows=[json.loads(s) for s in path.read_text().splitlines()]
        assert rows[-1]==dict(type='complete',source_unchanged=True)
        m=rows[0]; assert m['source_hashes']==plan['sources'][variant]
        assert m['driver_sha256']==sha(HERE/'bench.py') and m['plan_sha256']==sha(HERE/'plan.json')
        assert m['variant']==variant and m['lane']==lane
        assert rows[1]['type']=='checks' and rows[1]['ABA']
        assert rows[1]['perft_positions']==6 and rows[1]['ordering_cases']==96
        probes={(r['id'],r['repeat']):r for r in rows if r['type']=='probe'}
        assert len(probes)==24 and len(rows)==27
        data[lane,variant]=probes; metadata.append(m)
base=data['a','narrow']
ident=lambda r:(r['uci'],r['info']['score'],r['info']['depth'],r['info']['nodes'],r['info']['aborted'],[(v[0],v[1],v[2],v[3],v[5]) for v in r['info']['trace']])
for probes in data.values():
    assert probes.keys()==base.keys()
    for k,r in probes.items(): assert ident(r)==ident(base[k]), (k,r); compared+=1
effects={}
for variant in plan['variants'][1:]:
    lanes={}
    for lane in plan['lanes']:
        ratios=[data[lane,'narrow'][k]['seconds']/data[lane,variant][k]['seconds'] for k in base]
        lanes[lane]=math.exp(sum(map(math.log,ratios))/len(ratios))
    effects[variant]=dict(speed_ratio_by_lane=lanes,geometric_speed_ratio=math.sqrt(lanes['a']*lanes['b']),positive_both_lanes=all(v>1 for v in lanes.values()))
result=dict(audit='PASS',search_identity_runs=compared,unique_roots=12,
    ordering_checks=768,perft_checks=48,cold_seconds=[m['cold_seconds'] for m in metadata],effects=effects,
    limits='Twelve selected development roots at 200k nodes, two repeats per lane. Search identity includes completed iteration results and work, not just final move. Mirrored two-core Linux timing is not independent playing-strength evidence or the untouched referee gate. No release promotion.',
    evidence={p.name:sha(p) for p in HERE.glob('*.jsonl')},plan_sha256=sha(HERE/'plan.json'))
(HERE/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
