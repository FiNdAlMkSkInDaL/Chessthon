"""Windows correctness-only policy parity; never a Linux timing claim."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import json,sys,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(8)['applied'];src=HERE/'native-policy-r1/allocate';sys.path.insert(0,str(src));start=time.perf_counter()
import agent,core_nb as c
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert c.NUMBA_READY and c.root_search_nb.nopython_signatures
maximum=np.zeros(32);count=0
for r in json.loads((HERE/'native-policy-r1/policy-cases.json').read_text()):
    pos=from_fen(r['fen']);move=next(m for m in generate_legal(pos) if move_uci(m)==r['uci']);bb,mb,st=c.pack_pos(pos);saved=[v.copy() for v in (bb,mb,st)]
    undo=np.zeros(7,np.uint64);before=c.evaluate_nb(bb,st,False,c.NET,c.NN_LAST_BB,c.NN_ACC)
    f=c.policy_features_nb(bb,mb,st,move,undo,c.NET,c.NN_LAST_BB,c.NN_ACC,before);err=np.abs(f-np.array(r['features']));maximum=np.maximum(maximum,err)
    assert err[19]<.011 and np.max(np.delete(err,19))<1e-5,(r['uci'],f,r['features'])
    assert all(np.array_equal(a,b) for a,b in zip((bb,mb,st),saved));count+=1
report=dict(scope='Windows correctness only',features=count,maximum_errors=maximum.tolist(),elapsed=time.perf_counter()-start)
(HERE/'local-policy-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
