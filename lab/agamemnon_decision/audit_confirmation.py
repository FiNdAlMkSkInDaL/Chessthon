"""Retain the frozen suite audit, replacing only its obsolete draw-claim predicate."""
import argparse,inspect,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'lab/tempest_build/official-284724ab'));sys.path.insert(1,str(ROOT))
import chess
from lab.odin.release import validate_match as v
from lab.odin.release.plan import digest

def current(board):
    o=board.outcome()
    if o:return o
    if board.is_repetition(3):return chess.Outcome(chess.Termination.THREEFOLD_REPETITION,None)
    if board.is_fifty_moves():return chess.Outcome(chess.Termination.FIFTY_MOVES,None)
    return None

code=inspect.getsource(v.validate_game)
assert code.count('board.outcome(claim_draw=True)')==2
code=code.replace('board.outcome(claim_draw=True)','_current_outcome(board)')
env=dict(v.__dict__,_current_outcome=current);exec(code,env);v.validate_game=env['validate_game']
ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,required=True);args=ap.parse_args()
out=args.directory;plan_path=out/'plan.json';plan=json.loads(plan_path.read_text())
paths=[out/'lane-a.jsonl',out/'lane-b.jsonl'];parsed=[v.read_log(p) for p in paths]
report=v.audit(plan,digest(plan_path),'confirmation',[(p.name,rows) for p,(rows,_) in zip(paths,parsed)])
errors=[e for _,errs in parsed for e in errs]
assert not errors,errors
games=[r for rows,_ in parsed for r in rows if r.get('type')=='game']
report['raw_score']=sum(g['candidate_points'] for g in games)/len(games) if games else None
report['effect_size_target_pass']=report['raw_score'] is not None and report['raw_score']>=.55
report['bounded_confirmation_pass']=report['verdict']=='PASS' and report['effect_size_target_pass']
report['automatic_promotion']=False
report['validation_function_sha256']=hashlib.sha256(code.encode()).hexdigest()
report['log_sha256']={p.name:digest(p) for p in paths}
(out/'audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
