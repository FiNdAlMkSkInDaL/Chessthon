"""Exact feature-state and fixed-node identity gates for the neural cache."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,inspect,json,sys,time
from pathlib import Path
import numpy as np,chess
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True);ap.add_argument('--cpu',type=int,default=0);a=ap.parse_args();os.sched_setaffinity(0,{a.cpu})
src=HERE/a.variant;sys.path.insert(0,str(src));started=time.perf_counter()
import agent,core_nb as c,history
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert c.NUMBA_READY and c.root_search_nb.nopython_signatures;cold=time.perf_counter()-started
bound={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir() if p.is_file() and p.suffix in ('.py','.npz')};manifest=json.loads((HERE/'manifest.json').read_text())
for name,value in bound.items():assert manifest['files'][f'{a.variant}/{name}']==value
snapshot={k:v.copy() for k,v in vars(c).items() if isinstance(v,np.ndarray) and v.flags.writeable}
original=inspect.getsource(c.search_root);fixed=original.replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative','max_nodes = _LAB_NODE_LIMIT');assert fixed!=original;wall=c.search_root;exec(compile(fixed,'<agamemnon-fixed-nodes>','exec'),c.__dict__)
with (HERE/f'{a.variant}-swapped-linux.jsonl').open('x') as out:
    def emit(r):out.write(json.dumps(r)+'\n');out.flush()
    emit(dict(type='metadata',source_hashes=bound,cold_seconds=cold,driver_sha256=hashlib.sha256(fixed.encode()).hexdigest(),scope='Used diagnostics, same learned quantized model across variants; not a release or independent strength test.'))
    for name,fen,expected in json.loads((HERE/'perft.json').read_text()):assert c.perft_pos(from_fen(fen),3)==expected['3'],name
    maximum=0;checks=0;cases=json.loads((HERE/'eval-cases.json').read_text())
    for r in cases:
        b=chess.Board(r['fen']);bb,mb,st=c.pack_pos(from_fen(b.fen()));extra=(c.NN_LAST_BB,c.NN_ACC) if a.variant=='delta' else ()
        value=int(c.evaluate_nb(bb,st,False,c.NET,*extra))*(1 if b.turn else -1);error=abs(value-r['expected_white_cp']);maximum=max(maximum,error);assert error<2.1,(r,value)
        if a.variant=='delta':
            expected=np.tile(c.NET[768].astype(np.int32),(2,1))
            for sq,piece in b.piece_map().items():
                p=piece.piece_type-1+(0 if piece.color else 6)
                expected[0]+=c.NET[p*64+sq].astype(np.int32);expected[1]+=c.NET[((p+6)%12)*64+(sq^56)].astype(np.int32)
            assert np.array_equal(expected,c.NN_ACC) and np.array_equal(bb,c.NN_LAST_BB)
        checks+=1
    emit(dict(type='checks',perft_positions=6,eval_positions=checks,max_rounding_cp=maximum,integer_cache_checks=checks if a.variant=='delta' else 0))
    def run(r,budget,kind):
        for k,v in snapshot.items():np.copyto(getattr(c,k),v)
        history.reset();b=chess.Board(r['start_fen']);own=r['storm_colour']=='white'
        for u in r['history_uci']:
            if b.turn==own:history.observe_served(b);history.observe_our_uci(b,u)
            b.push_uci(u)
        assert b.fen()==r['fen'];history.observe_served(b);p=from_fen(b.fen());c._LAB_NODE_LIMIT=budget;t=time.perf_counter()
        fn=wall if kind=='wall' else c.search_root;ms=budget if kind=='wall' else 1e12
        move=fn(p,generate_legal(p),ms,ms,False,history.zkeys().copy());uci=move_uci(move);assert chess.Move.from_uci(uci) in b.legal_moves
        return dict(type='probe',id=r['id'],kind=kind,budget=budget,uci=uci,seconds=time.perf_counter()-t,info=c.last_info())
    roots=json.loads((HERE/'cases.json').read_text())
    first=run(roots[0],20000,'nodes');run(roots[-1],20000,'nodes');again=run(roots[0],20000,'nodes');assert (first['uci'],first['info']['nodes'],first['info']['score'])==(again['uci'],again['info']['nodes'],again['info']['score']);emit(dict(type='isolation',ABA=True))
    for r in roots:
        for budget in (200000,1000000):emit(run(r,budget,'nodes'))
        for ms in (500,2000):emit(run(r,ms,'wall'))
    for name,value in bound.items():assert hashlib.sha256((src/name).read_bytes()).hexdigest()==value
    emit(dict(type='complete'))
print(a.variant,'complete',round(cold,3),flush=True)
