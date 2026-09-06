"""Finite-reference review of predeclared time points in the completed value screen."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import io,json,sys
from pathlib import Path
import chess,chess.pgn,chess.engine,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity
from policy import EXE,sha
assert apply_windows_affinity(6)['applied'];outdir=HERE/'value-match-review';outdir.mkdir(exist_ok=False)
plan=dict(plies=[12,24,48,72],nodes=64000,script_sha256=sha(__file__),teacher_sha256=sha(EXE),scope='Finite-reference diagnostics, not exact minimax. Both players sampled at nearest next turn to each fixed game-relative ply. Not selected by reference outcome. These match families are already development.')
(outdir/'plan.json').write_text(json.dumps(plan,indent=2));rows=[]
def reference(engine,b,move=None):
    engine.configure({'Clear Hash':None});latest=None
    with engine.analysis(b,chess.engine.Limit(nodes=64000),root_moves=[move] if move else None,game=object()) as analysis:
        for info in analysis:
            if info.get('score') is not None and info.get('pv') and not info.get('lowerbound') and not info.get('upperbound'):latest=dict(info)
    assert latest is not None
    return dict(cp=latest['score'].pov(b.turn).score(mate_score=10000),depth=latest['depth'],nodes=latest['nodes'],pv=[m.uci() for m in latest['pv']])
with (outdir/'labels.jsonl').open('x') as out,chess.engine.SimpleEngine.popen_uci(str(EXE)) as engine:
    engine.configure({'Threads':1,'Hash':32})
    for lane in (0,1):
        games=[r for r in map(json.loads,(HERE/f'match-value-r1/lane{lane}.jsonl').open()) if r['type']=='game']
        for g in games:
            game=chess.pgn.read_game(io.StringIO(g['pgn']));b=game.board();wanted=set()
            for point in plan['plies']:
                for role in ('candidate','baseline'):
                    eligible=[i for i,r in enumerate(g['telemetry']) if i>=point and r['role']==role]
                    if eligible:wanted.add(eligible[0])
            for i,m in enumerate(game.mainline_moves()):
                if i in wanted:
                    t=g['telemetry'][i];best=reference(engine,b);chosen=best if best['pv'][0]==m.uci() else reference(engine,b,m)
                    r=dict(lane=lane,game=g['game'],opening=g['opening_index'],ply=i,role=t['role'],fen=b.fen(),move=m.uci(),engine_score=t['score'],engine_depth=t['depth'],reference=best,chosen=chosen,regret=max(0,best['cp']-chosen['cp']))
                    rows.append(r);out.write(json.dumps(r)+'\n');out.flush()
                b.push(m)
    out.write(json.dumps(dict(type='complete'))+'\n')
report={}
for role in ('candidate','baseline'):
    rr=[r for r in rows if r['role']==role];report[role]=dict(n=len(rr),mean_regret_cp=float(np.mean([r['regret'] for r in rr])),regret_over_200=sum(r['regret']>200 for r in rr),score_mae=float(np.mean([abs(r['engine_score']-r['reference']['cp']) for r in rr])),optimistic_by_200=sum(r['engine_score']-r['reference']['cp']>200 for r in rr))
(outdir/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
