import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((HERE/'plan.json').read_text());allrows={}
for name in ['queen-gate','graded-gate','capture-gate','control-tt-linux','tt_instrument-tt-linux']:
    rows=[json.loads(s) for s in (HERE/f'{name}.jsonl').read_text().splitlines()]
    assert rows[-1]==dict(type='complete',source_unchanged=True)
    m=rows[0];v=m['variant'];assert m['source_hashes']==plan['sources'][v]
    assert m['script_sha256']==sha(HERE/'probe.py')
    casefile=HERE/('tt-cases.json' if name.endswith('linux') else 'gate-cases.json')
    assert m['cases_sha256']==sha(casefile)
    assert rows[1]['perft_positions']==6 and rows[1]['predicate_checks']==18432 and rows[1]['ABA']
    probes=[r for r in rows if r['type']=='probe'];assert len(probes)==(8 if name.endswith('linux') else 18)
    allrows[name]=probes
ident=lambda r:(r['id'],r['budget'],r['uci'],r['info']['depth'],r['info']['score'],r['info']['nodes'],[(v[0],v[1],v[2],v[3],v[5]) for v in r['info']['trace']])
assert list(map(ident,allrows['control-tt-linux']))==list(map(ident,allrows['tt_instrument-tt-linux']))
tt=allrows['tt_instrument-tt-linux'];material=[r for r in tt if r['tt_stats'][4]/max(1,r['tt_stats'][0])>=.005 or r['tt_stats'][3]>=100]
capture=allrows['capture-gate'];assert any(r['capture_history']['root_order_changed'] for r in capture)
result=dict(audit='PASS',native_variants=['queen','graded','capture'],tt_instrument_identity=True,
    tt_gate_passed=bool(material),tt_gate_roots=[dict(id=r['id'],nodes=r['budget'],stats=r['tt_stats']) for r in material],
    capture_roots_with_learned_reorder=sum(r['capture_history']['root_order_changed'] for r in capture),
    evidence_sha256={name:sha(HERE/f'{name}.jsonl') for name in allrows})
(HERE/'probe-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
