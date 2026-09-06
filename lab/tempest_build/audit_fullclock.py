"""Audit the two current-rule full-clock smoke games without an Elo inference."""
import inspect,json,hashlib,sys
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(HERE/'official-284724ab'))
import chess
from lab.odin.release import validate_match as v
from lab.laptop_match import build_game_plan
from lab.odin.release.plan import source_provenance
def current(b):
    o=b.outcome()
    if o:return o
    if b.is_repetition(3):return chess.Outcome(chess.Termination.THREEFOLD_REPETITION,None)
    if b.is_fifty_moves():return chess.Outcome(chess.Termination.FIFTY_MOVES,None)
    return None
stage=ROOT/'lab/odin/native_release/tempest-exact-r1';p=stage/'fullclock-pair.jsonl';rows,errors=v.read_log(p);assert not errors
assert rows[-1]['type']=='run_summary' and rows[-1]['protocol_failures']==0 and rows[-1]['games_completed']==2
start=next(r for r in rows if r['type']=='run_start');assert start['base_ms']==120000 and start['increment_ms']==500 and start['init_budget_s']==90 and start['ply_cap']==600
assert start['official_referee_unchanged'] and start['official_runner_unchanged'] and not start['ready_override'] and start['runner_shim'] is None
assert start['source_provenance']==source_provenance(ROOT,HERE/'official-284724ab')
assert start['runtime']['machine']=='x86_64' and start['runtime']['python'].startswith('3.12.')
assert start['thread_env']=={k:'1' for k in v.THREADS}
suite={'candidate_sha256':'0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4','baseline_sha256':'cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647'}
for role in ('candidate','baseline'):assert start[role]['sha256']==suite[role+'_sha256'] and start[role]['private_snapshot_verified']
fpath=ROOT/'lab/odin/release_openings/development.fen';assert hashlib.sha256(fpath.read_bytes()).hexdigest()==start['openings_sha256']
fens=[s for s in fpath.read_text().splitlines() if s.strip() and not s.startswith('#')]
plans=[asdict(r) for r in build_game_plan(fens,1,0,(0,0))];assert start['plans']==plans
# Keep all existing archive/resource/clock/replay checks; only replace the
# superseded intended-move terminal predicate in this isolated lab invocation.
code=inspect.getsource(v.validate_game);assert code.count('board.outcome(claim_draw=True)')==2
code=code.replace('board.outcome(claim_draw=True)','_current_outcome(board)');env=dict(v.__dict__,_current_outcome=current);exec(code,env)
games=[r for r in rows if r['type']=='game'];assert len(games)==2
replays=[]
for game,plan in zip(games,plans):replays.append(env['validate_game'](game,start,plan,suite,errors))
assert not errors,errors
units=[u for r in replays for u in r['units']];assert len(set(units))==4
headroom=[];cold=[]
for g in games:
    color=g['candidate_colour'];timing=g[color+'_timing'];cold.append(timing['init_s'])
    headroom.extend(m['time_left_ms']-m['elapsed_ms'] for m in timing['moves'])
report=dict(audit='PASS',games=2,results=[dict(candidate_colour=g['candidate_colour'],points=g['candidate_points'],termination=g['termination']) for g in games],operational_failures=0,legal_plies=sum(r['plies'] for r in replays),candidate_cold_import_s=cold,min_candidate_request_headroom_ms=min(headroom),fresh_processes=len(set(units)),log_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),validation_function_sha256=hashlib.sha256(code.encode()).hexdigest(),scope='Two full 120+0.5 wall-clock smoke games, exact current referee, fresh processes, CPU/RAM/no-swap/source/clock audit; not a strength estimate.')
(stage/'fullclock-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
