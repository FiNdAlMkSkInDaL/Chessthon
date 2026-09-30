"""Deterministic stratified reanalysis of old quiet labels; not training."""
import sys,json,hashlib,time
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(R))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(6)['applied']
import numpy as np,chess,chess.engine
from lab.odin.new_games.review_new import reference
rows=[json.loads(s) for s in (R/'lab/odin/quiet_eval/fit-records.jsonl').read_text().splitlines()]
z=np.load(R/'lab/odin/quiet_eval/expanded-matrix.npz');phase=z['phase'][:,0];chosen=[]
for lo,hi in [(0,.25),(.25,.75),(.75,1.01)]:
    indices=[i for i in range(len(rows)) if lo<=phase[i]<hi]
    chosen+=sorted(indices,key=lambda i:hashlib.sha256(('tempest-label-audit'+rows[i]['id']).encode()).hexdigest())[:40]
plan={'indices':chosen,'ids':[rows[i]['id'] for i in chosen],'budget':1000000,'history':'Only resolved FEN available in fit-records; no reconstructed PGN history. Cannot attribute all differences solely to node depth.'}
(H/'label-audit-plan.json').write_text(json.dumps(plan,indent=2))
exe='stockfish'
with chess.engine.SimpleEngine.popen_uci(exe) as e,(H/'label-audit.jsonl').open('x') as out:
    e.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
    for i in chosen:
        r=rows[i];b=chess.Board(r['fen']);deep=reference(e,b,1000000);row=dict(id=r['id'],fen=r['fen'],phase=float(phase[i]),split=r['split'],old_cp=r['reference_cp'],deep=deep,delta_cp=deep['white_cp']-r['reference_cp'])
        out.write(json.dumps(row)+'\n');out.flush()
print('done',len(chosen))
