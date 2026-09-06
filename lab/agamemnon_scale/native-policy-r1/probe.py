"""Linux cold, native feature, state isolation and decision-cost gates."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,inspect,json,sys,time
from pathlib import Path
import numpy as np,chess
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True);ap.add_argument('--cpu',type=int,required=True);a=ap.parse_args();os.sched_setaffinity(0,{a.cpu})
src=HERE/a.variant;sys.path.insert(0,str(src));start=time.perf_counter()
import agent,core_nb as c,history
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert c.NUMBA_READY and c.root_search_nb.nopython_signatures;cold=time.perf_counter()-start
assert cold<80,cold
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((HERE/'manifest.json').read_text());bound={p.name:sha(p) for p in src.iterdir() if p.is_file() and p.suffix in ('.py','.npz')}
for name,h in bound.items():assert manifest['files'][f'{a.variant}/{name}']==h
snapshot={k:v.copy() for k,v in vars(c).items() if isinstance(v,np.ndarray) and v.flags.writeable}
original=inspect.getsource(c.search_root);fixed=original.replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative','max_nodes = _LAB_NODE_LIMIT');assert fixed!=original;wall=c.search_root;exec(compile(fixed,'<scale-fixed-nodes>','exec'),c.__dict__)
with (HERE/f'{a.variant}-linux.jsonl').open('x') as out:
    def emit(r):out.write(json.dumps(r)+'\n');out.flush()
    emit(dict(type='metadata',source_hashes=bound,cold_seconds=cold,scope='Linux one CPU research gate, not the complete no-network release sandbox. Used diagnostic roots.'))
    for name,fen,expected in json.loads((HERE/'perft.json').read_text()):assert c.perft_pos(from_fen(fen),3)==expected['3'],name
    maximum=0;checks=0
    if hasattr(c,'NET'):
        for r in json.loads((HERE/'eval-cases.json').read_text()):
            b=chess.Board(r['fen']);bb,mb,st=c.pack_pos(from_fen(b.fen()));value=int(c.evaluate_nb(bb,st,False,c.NET,c.NN_LAST_BB,c.NN_ACC))*(1 if b.turn else -1);err=abs(value-r['expected_white_cp']);maximum=max(maximum,err);assert err<2.1,(r,value)
            expected=np.tile(c.NET[768].astype(np.int32),(2,1))
            for sq,piece in b.piece_map().items():
                p=piece.piece_type-1+(0 if piece.color else 6);expected[0]+=c.NET[p*64+sq].astype(np.int32);expected[1]+=c.NET[((p+6)%12)*64+(sq^56)].astype(np.int32)
            assert np.array_equal(expected,c.NN_ACC) and np.array_equal(bb,c.NN_LAST_BB);checks+=1
    emit(dict(type='checks',perft_positions=6,integer_cache_checks=checks,max_rounding_cp=maximum))
    if hasattr(c,'POLICY'):
        maximum=np.zeros(32);count=0
        for r in json.loads((HERE/'policy-cases.json').read_text()):
            pos=from_fen(r['fen']);move=next(m for m in generate_legal(pos) if move_uci(m)==r['uci']);bb,mb,st=c.pack_pos(pos);saved=[v.copy() for v in (bb,mb,st)]
            undo=np.zeros(16,np.uint64);before=c.evaluate_nb(bb,st,False,c.NET,c.NN_LAST_BB,c.NN_ACC)
            f=c.policy_features_nb(bb,mb,st,move,undo,c.NET,c.NN_LAST_BB,c.NN_ACC,before);error=np.abs(f-np.array(r['features']));maximum=np.maximum(maximum,error)
            assert error[19]<.011 and np.max(np.delete(error,19))<1e-5,(r['uci'],f,r['features'])
            assert all(np.array_equal(a,b) for a,b in zip((bb,mb,st),saved));count+=1
        for depth in range(5,30):
            for n in (2,3,32,218):
                rr=[c.learned_reduction_nb(depth,n,p) for p in (.001,.01,.1,.5,.99)]
                assert all(0<=r<=depth-3 for r in rr) and rr==sorted(rr,reverse=True)
        emit(dict(type='policy_checks',features=count,max_errors=maximum.tolist(),minimum_child_depth=2,monotonic=True))
    def run(r,budget,kind):
        for k,v in snapshot.items():np.copyto(getattr(c,k),v)
        history.reset();b=chess.Board(r['start_fen']);own=r['storm_colour']=='white'
        for u in r['history_uci']:
            if b.turn==own:history.observe_served(b);history.observe_our_uci(b,u)
            b.push_uci(u)
        assert b.fen()==r['fen'];history.observe_served(b);p=from_fen(b.fen());c._LAB_NODE_LIMIT=budget;t=time.perf_counter();ms=budget if kind=='wall' else 1e12
        move=(wall if kind=='wall' else c.search_root)(p,generate_legal(p),ms,ms,False,history.zkeys().copy());uci=move_uci(move);assert chess.Move.from_uci(uci) in b.legal_moves
        return dict(type='probe',id=r['id'],kind=kind,budget=budget,uci=uci,seconds=time.perf_counter()-t,info=c.last_info(),policy_stats=c.POLICY_STATS.tolist() if hasattr(c,'POLICY_STATS') else None)
    roots=json.loads((HERE/'cases.json').read_text());first=run(roots[0],20000,'nodes');run(roots[-1],20000,'nodes');again=run(roots[0],20000,'nodes');assert (first['uci'],first['info']['nodes'],first['info']['score'])==(again['uci'],again['info']['nodes'],again['info']['score']);emit(dict(type='isolation',ABA=True))
    for r in roots:
        for budget in (200000,1000000):emit(run(r,budget,'nodes'))
        for ms in (500,2000):emit(run(r,ms,'wall'))
    for name,h in bound.items():assert sha(src/name)==h
    emit(dict(type='complete'))
print(a.variant,'complete',round(cold,3),flush=True)
