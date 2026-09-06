"""Immutable source-bound fixed-node identity/throughput and ordering checks."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'): os.environ[k]='1'
import argparse
import hashlib
import inspect
import json
import sys
import time
from pathlib import Path
import numpy as np
import chess

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
ap=argparse.ArgumentParser(); ap.add_argument('--variant',required=True); ap.add_argument('--lane',required=True); a=ap.parse_args()
plan=json.loads((HERE/'plan.json').read_text()); assert a.variant in plan['variants'] and a.lane in plan['lanes']
source=HERE/'prototypes'/a.variant
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def hashes(): return {p.name:sha(p) for p in source.iterdir() if p.is_file() and p.suffix in ('.py','.npz')}
assert hashes()==plan['sources'][a.variant]
assert sha(HERE/'cases.json')==plan['cases_sha256']
sys.path[:0]=[str(source),str(ROOT)]
t=time.perf_counter()
import agent,core_nb as core,history
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
cold=time.perf_counter()-t
assert core.NUMBA_READY and core.root_search_nb.nopython_signatures
snapshot={k:v.copy() for k,v in vars(core).items() if isinstance(v,np.ndarray) and v.flags.writeable}
original=inspect.getsource(core.search_root)
fixed=original.replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative','max_nodes = _LAB_NODE_LIMIT')
assert fixed!=original
exec(compile(fixed,'<stack-fixed-nodes>','exec'),core.__dict__)
cases=json.loads((HERE/'cases.json').read_text())
def reset(c):
    for k,v in snapshot.items(): np.copyto(getattr(core,k),v)
    history.reset(); b=chess.Board(c['start_fen']); own=c['storm_colour']=='white'
    for u in c['history_uci']:
        if b.turn==own: history.observe_served(b); history.observe_our_uci(b,u)
        b.push_uci(u)
    assert b.fen()==c['fen']; history.observe_served(b)
    return b
def run(c,nodes):
    b=reset(c); pos=from_fen(b.fen(en_passant='fen')); legal=generate_legal(pos); core._LAB_NODE_LIMIT=nodes
    t=time.perf_counter(); m=core.search_root(pos,legal,1e12,1e12,False,history.zkeys().copy()); seconds=time.perf_counter()-t
    u=move_uci(m); assert chess.Move.from_uci(u) in b.legal_moves
    return dict(id=c['id'],uci=u,info=core.last_info().copy(),seconds=seconds)
out=HERE/f'{a.variant}-{a.lane}.jsonl'
with out.open('x') as f:
    def emit(r): f.write(json.dumps(r)+'\n'); f.flush()
    emit(dict(type='metadata',variant=a.variant,lane=a.lane,cold_seconds=cold,source_hashes=hashes(),driver_sha256=sha(Path(__file__)),plan_sha256=sha(HERE/'plan.json')))
    # Native sort must equal stable reference order, including equal and negative histories.
    rng=np.random.default_rng(20260906); checked=0
    for c in cases:
        b=reset(c); pos=from_fen(b.fen(en_passant='fen')); bb,mb,st=core.pack_pos(pos); moves=generate_legal(pos)
        before=[x.copy() for x in (bb,mb,st)]
        for trial in range(8):
            hs=np.zeros_like(core.HISTORY) if trial==0 else rng.integers(-core.HISTORY_MAX,core.HISTORY_MAX+1,size=core.HISTORY.shape,dtype=np.int32)
            killers=np.zeros_like(core.KILLERS); ply=trial
            if len(moves)>=3: killers[ply,:]=moves[-2:]
            hm=moves[0] if trial%2 else 0
            shuffled=np.array(moves,np.int32); rng.shuffle(shuffled)
            expected=sorted(list(shuffled),key=lambda m:core.order_key(mb,m,ply,hm,killers,hs))
            core.sort_moves(mb,shuffled,len(shuffled),ply,hm,killers,hs)
            assert list(shuffled)==expected; checked+=1
        assert all(np.array_equal(x,y) for x,y in zip(before,(bb,mb,st)))
    from lab.perft import POSITIONS
    for name,fen,expected in POSITIONS: assert core.perft_pos(from_fen(fen),3)==expected[3]
    x=run(cases[0],20000); run(cases[-1],20000); y=run(cases[0],20000)
    identity=lambda r:(r['uci'],r['info']['score'],r['info']['nodes'],r['info']['depth'])
    assert identity(x)==identity(y)
    emit(dict(type='checks',ordering_cases=checked,perft_positions=len(POSITIONS),ABA=True))
    for repeat in range(plan['repeats']):
        for c in cases:
            r=run(c,plan['nodes']); emit(dict(type='probe',repeat=repeat,**r))
        print(a.variant,a.lane,'repeat',repeat,'complete',flush=True)
    assert hashes()==plan['sources'][a.variant]
    emit(dict(type='complete',source_unchanged=True))
