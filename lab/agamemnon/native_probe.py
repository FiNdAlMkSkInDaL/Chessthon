"""One-core source-bound native search bridge measurement, no match claim."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json,sys,time
from pathlib import Path
import numpy as np,chess
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True);ap.add_argument('--cpu',type=int,default=0);a=ap.parse_args()
os.sched_setaffinity(0,{a.cpu});src=HERE/a.variant;sys.path.insert(0,str(src));t=time.perf_counter()
import agent,core_nb as c,history
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert c.NUMBA_READY and c.root_search_nb.nopython_signatures
cold=time.perf_counter()-t;snapshot={k:v.copy() for k,v in vars(c).items() if isinstance(v,np.ndarray) and v.flags.writeable}
manifest=json.loads((HERE/'manifest.json').read_text());bound={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir() if p.is_file() and p.suffix in ('.py','.npz')}
for name,value in bound.items():assert manifest['files'][f'{a.variant}/{name}']==value
with (HERE/f'{a.variant}-linux.jsonl').open('x') as out:
    def emit(r):out.write(json.dumps(r)+'\n');out.flush()
    emit(dict(type='metadata',cold_seconds=cold,source_hashes=bound,affinity=list(os.sched_getaffinity(0)),scope='Native feasibility and used root diagnostics; not independent/full-clock games.'))
    for name,fen,expected in json.loads((HERE/'perft.json').read_text()):
        assert c.perft_pos(from_fen(fen),3)==expected['3'],name
    maximum=0
    if a.variant=='acc32':
        for r in json.loads((HERE/'eval-cases.json').read_text()):
            b=chess.Board(r['fen']);bb,mb,st=c.pack_pos(from_fen(b.fen()));v=int(c.evaluate_nb(bb,st,False,c.NET))*(1 if b.turn else -1);error=abs(v-r['expected_white_cp']);maximum=max(maximum,error);assert error<2.1,(r,v)
    emit(dict(type='checks',perft_positions=6,eval_parity_positions=300 if a.variant=='acc32' else 0,max_eval_rounding_cp=maximum))
    cases=json.loads((HERE/'cases.json').read_text())
    def run(r,ms):
        for k,v in snapshot.items():np.copyto(getattr(c,k),v)
        history.reset();b=chess.Board(r['start_fen']);own=r['storm_colour']=='white'
        for u in r['history_uci']:
            if b.turn==own:history.observe_served(b);history.observe_our_uci(b,u)
            b.push_uci(u)
        assert b.fen()==r['fen'];history.observe_served(b);p=from_fen(b.fen());t=time.perf_counter();move=c.search_root(p,generate_legal(p),ms,ms,False,history.zkeys().copy());elapsed=time.perf_counter()-t;uci=move_uci(move);assert chess.Move.from_uci(uci) in b.legal_moves
        return dict(type='probe',id=r['id'],budget_ms=ms,uci=uci,seconds=elapsed,info=c.last_info())
    for r in cases:
        for ms in (500,2000):emit(run(r,ms))
    for name,value in bound.items():assert hashlib.sha256((src/name).read_bytes()).hexdigest()==value
    emit(dict(type='complete'))
print(a.variant,'complete',round(cold,3),flush=True)
