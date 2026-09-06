"""Replay and summarize fixed-node development games; no Elo confidence claim."""
import argparse,collections,hashlib,io,json,statistics
from pathlib import Path
import chess,chess.pgn
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ap=argparse.ArgumentParser();ap.add_argument('--complete',action='store_true');ap.add_argument('--results',type=Path,default=HERE/'results');ap.add_argument('--expected-candidates',type=int,default=2);ap.add_argument('--out',type=Path,default=HERE/'screen-report.json');args=ap.parse_args()
rows={};errors=[]
fens=(HERE/'screen-openings/openings.fen').read_text().splitlines()
for path in sorted(args.results.glob('*.jsonl')):
    raw=[json.loads(s) for s in path.read_text().splitlines()]
    plan=raw[0];candidate=plan['candidate'];r=rows.setdefault(candidate,{'games':[],'workers':[],'platforms':collections.defaultdict(list),'lanes':[]})
    gs=[v for v in raw if v['type']=='game'];ws=[v for v in raw if v['type']=='worker']
    platform='linux' if 'linux' in path.name else 'windows'
    r['lanes'].append({'name':path.name,'games':len(gs),'complete':raw[-1]['type']=='summary','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    for w in ws:
        assert w['isolation']['pass'] and not w['metadata']['readiness_override']
        src=ROOT/('odin_submission' if w['role']=='baseline' else candidate)
        assert w['metadata']['source_hashes']=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(src.glob('*.py'))}
    for g in gs:
        pgn=chess.pgn.read_game(io.StringIO(g['pgn']));assert pgn and not pgn.errors
        b=pgn.board();assert b.fen()==chess.Board(fens[g['opening_index']]).fen()
        moves=list(pgn.mainline_moves());assert len(moves)==len(g['telemetry'])==g['plies']
        for m,t in zip(moves,g['telemetry']):
            assert b.outcome(claim_draw=True) is None and b.ply()<600
            assert m in b.legal_moves and m.uci()==t['uci'];b.push(m)
        outcome=b.outcome(claim_draw=True)
        assert (outcome and outcome.result()==g['result'] and outcome.termination.name==g['termination']) or (outcome is None and b.ply()>=600 and g['result']=='1/2-1/2')
        pts=.5 if g['result']=='1/2-1/2' else float((g['result']=='1-0')==(g['candidate_colour']=='white'))
        assert pts==g['candidate_points']
    r['games'].extend(gs);r['workers'].extend(ws);r['platforms'][platform].extend(gs)
report={}
def score(gs):
    c=collections.Counter(g['candidate_points'] for g in gs)
    return {'games':len(gs),'wins':c[1.0],'draws':c[.5],'losses':c[0.0],'score':sum(g['candidate_points'] for g in gs)/len(gs) if gs else None}
for name,r in rows.items():
    keys=[(g['opening_index'],g['candidate_colour']) for g in r['games']];assert len(keys)==len(set(keys))
    if args.complete:assert set(keys)=={(i,c) for i in range(24) for c in ('white','black')} and all(l['complete'] for l in r['lanes']) and len(r['workers'])==2*len(r['lanes'])
    baselines=[tuple(w['isolation']['first'][k] for k in ('uci','depth','score','nodes')) for w in r['workers'] if w['role']=='baseline']
    assert len(set(baselines))<=1,'Cold baseline workers disagree across CPUs/platforms'
    report[name]={**score(r['games']),'platforms':{p:score(gs) for p,gs in r['platforms'].items()},'lanes':r['lanes'],
        'median_game_seconds':statistics.median(g['seconds'] for g in r['games']) if r['games'] else None,
        'cold_import_seconds':[w['metadata']['cold_seconds'] for w in r['workers']],
        'reset_seconds':[w['isolation']['reset_seconds'] for w in r['workers']],
        'baseline_cold_worker_agreement':bool(baselines),'replayed_plies':sum(g['plies'] for g in r['games'])}
if args.complete:
    assert len(report)==args.expected_candidates
    ranked=sorted(report,key=lambda n:(report[n]['score'],n=='odin_v6_aspiration'),reverse=True)
    selected=ranked[0] if report[ranked[0]]['score']>.5 else None
    result={'complete':True,'selected':selected,'exploratory_only':True,'candidates':report}
    args.out.write_text(json.dumps(result,indent=2)+'\n')
else:result={'complete':False,'candidates':report}
print(json.dumps(result,indent=2))
