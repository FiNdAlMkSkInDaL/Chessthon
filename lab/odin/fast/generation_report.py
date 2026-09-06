"""Audit complete generation games and rank only completed candidates."""
import argparse,collections,hashlib,io,json,statistics
from pathlib import Path
import chess,chess.pgn
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--policy',type=Path,default=HERE/'generation-policy.json');ap.add_argument('--results',type=Path,default=HERE/'generation-results');ap.add_argument('--openings',type=Path,default=HERE/'generation-openings/screen.fen');ap.add_argument('--complete',action='store_true');ap.add_argument('--output',type=Path,default=HERE/'generation-report.json');args=ap.parse_args()
policy=json.loads(args.policy.read_text());jobs={r['name']:r for r in policy['generation']};fens=args.openings.read_text().splitlines();report=[]
for path in sorted(args.results.glob('*.jsonl')):
    raw=[json.loads(s) for s in path.read_text().splitlines()];plan=raw[0];name=plan['candidate'];job=jobs[name]
    assert plan['policy_sha256']==hashlib.sha256(args.policy.read_bytes()).hexdigest()
    assert plan['openings_sha256']==hashlib.sha256(args.openings.read_bytes()).hexdigest()
    assert plan['node_limit']==policy.get('nodes',policy.get('stage1',{}).get('nodes'))
    gs=[r for r in raw if r['type']=='game'];ws=[r for r in raw if r['type']=='worker'];complete=raw[-1]['type']=='summary';errors=[r for r in raw if r['type']=='error']
    if complete:assert len(gs)==2*len(fens) and len(ws)==2 and not errors
    for w in ws:
        assert w['isolation']['pass'] and w['metadata']['silent_native_fallback_rejected']
        expected=job['hashes'] if w['role']=='candidate' else {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'odin_submission').glob('*.py')}
        assert w['metadata']['source_hashes']==expected
    for g in gs:
        pgn=chess.pgn.read_game(io.StringIO(g['pgn']));assert pgn and not pgn.errors
        b=pgn.board();assert b.fen()==chess.Board(fens[g['opening_index']]).fen()
        moves=list(pgn.mainline_moves());assert len(moves)==g['plies']==len(g['telemetry'])
        for m,t in zip(moves,g['telemetry']):
            assert b.outcome(claim_draw=True) is None and b.ply()<600 and m in b.legal_moves and m.uci()==t['uci']
            assert 0<=t['nodes']<=plan['node_limit']+1
            b.push(m)
        outcome=b.outcome(claim_draw=True)
        assert (outcome and outcome.result()==g['result'] and outcome.termination.name==g['termination']) or (not outcome and b.ply()>=600 and g['result']=='1/2-1/2')
        points=.5 if g['result']=='1/2-1/2' else float((g['result']=='1-0')==(g['candidate_colour']=='white'))
        assert points==g['candidate_points']
    keys=[(g['opening_index'],g['candidate_colour']) for g in gs];assert len(keys)==len(set(keys))
    if complete:assert set(keys)=={(i,c) for i in range(len(fens)) for c in ('white','black')}
    count=collections.Counter(g['candidate_points'] for g in gs)
    parameters=job.get('parameter_count',sum(len(v) if isinstance(v,dict) else 1 for v in job['config'].values()))
    report.append({'name':name,'complete':complete,'games':len(gs),'wins':count[1.0],'draws':count[.5],'losses':count[0.0],
                   'points':sum(g['candidate_points'] for g in gs),'score':sum(g['candidate_points'] for g in gs)/len(gs) if gs else None,
                   'replayed_plies':sum(g['plies'] for g in gs),'errors':errors,'parameters':parameters,'source':job['source'],'lane':job['lane'],
                   'seconds':raw[-1].get('seconds') if complete else None,'log_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
if args.complete:assert len(report)==len(jobs) and all(r['complete'] for r in report)
ranked=sorted([r for r in report if r['complete']],key=lambda r:(-r['score'],r['parameters'],r['name']))
result={'complete':len(ranked)==len(jobs),'exploratory_only':True,'ranking':[r['name'] for r in ranked],'candidates':report}
if args.complete:args.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
