"""Windows correctness preflight for mover/opponent heads, no runtime claim."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import json,sys,time
from pathlib import Path
import numpy as np,chess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(6)['applied'];src=HERE/'native-turn-r1/value';sys.path.insert(0,str(src));start=time.perf_counter()
import agent,core_nb as c
from board_nb import from_fen
assert c.NUMBA_READY and c.NET.shape==(773,32)
maximum=0.;checks=0
for r in json.loads((HERE/'native-turn-r1/eval-cases.json').read_text()):
    b=chess.Board(r['fen']);bb,mb,st=c.pack_pos(from_fen(b.fen()));v=c.evaluate_nb(bb,st,False,c.NET,c.NN_LAST_BB,c.NN_ACC)*(1 if b.turn else -1);err=abs(v-r['expected_white_cp']);maximum=max(maximum,err);assert err<2.1,(r,v);checks+=1
for name,fen,expected in json.loads((HERE/'native-turn-r1/perft.json').read_text()):assert c.perft_pos(from_fen(fen),3)==expected['3']
report=dict(scope='Windows correctness only',positions=checks,max_rounding_cp=maximum,perft_positions=6,elapsed=time.perf_counter()-start)
(HERE/'local-turn-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
