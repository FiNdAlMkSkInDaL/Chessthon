"""Controlled offline conversion diagnostic; reference defender is never shipped."""
import os,sys,inspect,json,time,argparse
from pathlib import Path
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tempest'));sys.path.insert(0,str(HERE))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(4)['applied']
import chess,chess.engine,chess.pgn
from review_v6_games import terminal,EXE
sys.path.insert(0,str(ROOT/'tempest'))
import agent,core_nb as c,storm_clock
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
ap=argparse.ArgumentParser();ap.add_argument('--fixed-nodes',type=int,default=0);args=ap.parse_args()
assert c.NUMBA_READY
assert Path(agent.__file__).resolve().parent==ROOT/'tempest'
assert Path(c.__file__).resolve().parent==ROOT/'tempest'
if args.fixed_nodes:
    driver=inspect.getsource(c.search_root).replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative',f'max_nodes = {args.fixed_nodes}')
    exec(compile(driver,'<fixed-node-conversion>','exec'),c.__dict__)
original=storm_clock.SearchClock.should_start
s=inspect.getsource(original);s=inspect.cleandoc(s)
# cleandoc removes the method indentation, retaining relative body indentation.
import textwrap
s=textwrap.dedent(inspect.getsource(original)).replace('self.root_moves == 1 or latest.score >= MATE_THRESHOLD','self.root_moves == 1')
env=dict(storm_clock.__dict__);exec(s,env);continued=env['should_start']
with next((ROOT/'Chess_results_day3').glob('*round-35-*.pgn')).open() as f:g=chess.pgn.read_game(f)
b=g.board();starts=[]
for n in g.mainline():
    b.push(n.move)
    if b.turn and b.fullmove_number in (79,89):starts.append((f'round35-move{b.fullmove_number}',b.copy()))
starts.extend([('queen-distant',chess.Board('7k/8/8/8/8/8/8/KQ6 w - - 0 1')),('queen-clock80',chess.Board('7k/8/8/8/8/8/8/KQ6 w - - 80 50'))])
out=HERE/('mate-conversion-nodes.jsonl' if args.fixed_nodes else 'mate-conversion.jsonl')
with chess.engine.SimpleEngine.popen_uci(str(EXE)) as e,out.open('x') as f:
    e.configure({'Threads':1,'Hash':32})
    def emit(r):f.write(json.dumps(r)+'\n');f.flush()
    emit(dict(type='plan',own_wall_ms=None if args.fixed_nodes else 100,own_node_cap=args.fixed_nodes or None,defender_nodes=20000,starts=[(k,b.fen()) for k,b in starts],policies=['baseline','continue_mate'],scope='Finite offline defensive reference, diagnostic only; no Elo inference'))
    for policy,method in [('baseline',original),('continue_mate',continued)]:
        storm_clock.SearchClock.should_start=method
        for name,initial in starts:
            for key in ('TT_KEY','TT_MOVE','TT_SCORE','TT_DEPTH','TT_GEN','TT_AGE','KILLERS','HISTORY'):getattr(c,key).fill(0)
            b=initial.copy();z=[];replay=chess.Board(initial.root().fen())
            for m in initial.move_stack:z.append(from_fen(replay.fen()).key);replay.push(m)
            trace=[];total=0
            for ply in range(120):
                finish=terminal(b)
                if finish:break
                p=from_fen(b.fen());z.append(p.key)
                if b.turn:
                    budget=1e12 if args.fixed_nodes else 100.
                    t=time.perf_counter();m=c.search_root(p,generate_legal(p),budget,budget,False,z);elapsed=time.perf_counter()-t;info=c.last_info()
                    u=move_uci(m);trace.append(dict(fen=b.fen(),uci=u,score=info['score'],depth=info['depth'],nodes=info['nodes'],ms=elapsed*1000));total+=elapsed
                else:
                    e.configure({'Clear Hash':None});u=e.play(b,chess.engine.Limit(nodes=20000),game=object()).move.uci()
                assert chess.Move.from_uci(u) in b.legal_moves;b.push_uci(u)
            finish=terminal(b)
            emit(dict(type='game',policy=policy,start=name,plies=len(b.move_stack)-len(initial.move_stack),outcome=finish.termination.name if finish else 'limit',white_moves=len(trace),search_seconds=total,trace=trace));print(policy,name,len(trace),finish,flush=True)
    emit(dict(type='complete'))
