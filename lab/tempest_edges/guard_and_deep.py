"""Native clock-route guard and longer diagnostics for the exploratory bundle."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import hashlib,inspect,json,sys,time
from pathlib import Path
import chess,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(6)['applied']
source=HERE/'prototypes/capture_tables';sys.path.insert(0,str(source));began=time.perf_counter()
import agent,core_nb as c,history,endgame_exact
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
cold=time.perf_counter()-began;assert c.NUMBA_READY
snapshot={k:v.copy() for k,v in vars(c).items() if isinstance(v,np.ndarray) and v.flags.writeable}
def reset():
    for k,v in snapshot.items():np.copyto(getattr(c,k),v)
    history.reset()
original_policy=endgame_exact.choose_syzygy;calls=[]
def counted(*args,**kwargs):calls.append(True);return original_policy(*args,**kwargs)
endgame_exact.choose_syzygy=counted
guard=[]
for ms in (1200,1199,500,100):
    reset();calls.clear();fen='8/k1P5/2K5/8/8/8/8/8 w - - 0 1';t=time.perf_counter();u=agent.get_move(fen,ms);elapsed=(time.perf_counter()-t)*1000
    assert chess.Move.from_uci(u) in chess.Board(fen).legal_moves
    assert bool(calls)==(ms>=1200) and elapsed<max(100,ms-200),(ms,calls,elapsed)
    if ms>=1200:assert u=='c7c8r'
    guard.append(dict(time_left_ms=ms,broader_table_used=bool(calls),uci=u,elapsed_ms=elapsed))
endgame_exact.choose_syzygy=original_policy
original=inspect.getsource(c.search_root)
fixed=original.replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative','max_nodes = _LAB_NODE_LIMIT')
exec(compile(fixed,'<bundle-fixed-nodes>','exec'),c.__dict__)
cases=json.loads((HERE/'gate-cases.json').read_text());cases=[r for r in cases if r['id'] in ('v6-r37-p37','r39-p84')]
with (HERE/'bundle-deep.jsonl').open('x') as f:
    def emit(r):f.write(json.dumps(r)+'\n');f.flush()
    emit(dict(type='metadata',cold_seconds=cold,guard=guard,source_hashes={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()},script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    for case in cases:
        for budget in (1000000,4000000,12000000):
            reset();b=chess.Board(case['start_fen']);own=case['storm_colour']=='white'
            for u in case['history_uci']:
                if b.turn==own:history.observe_served(b);history.observe_our_uci(b,u)
                b.push_uci(u)
            assert b.fen()==case['fen'];history.observe_served(b);pos=from_fen(b.fen(en_passant='fen'));c._LAB_NODE_LIMIT=budget
            t=time.perf_counter();m=c.search_root(pos,generate_legal(pos),1e12,1e12,False,history.zkeys().copy());seconds=time.perf_counter()-t;u=move_uci(m)
            assert chess.Move.from_uci(u) in b.legal_moves
            emit(dict(type='probe',id=case['id'],nodes=budget,uci=u,info=c.last_info().copy(),seconds=seconds));print(case['id'],budget,u,c.last_info()['score'],flush=True)
    emit(dict(type='complete'))
