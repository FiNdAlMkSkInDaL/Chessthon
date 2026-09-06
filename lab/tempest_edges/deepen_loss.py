"""Preselected early decisions and the critical queen trade, full-history labels."""
import hashlib,json,os,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE))
from review_loss import EXE,reference,pin_cpu4
import chess,chess.engine
pin_cpu4(os.getpid(),2)
rows=[json.loads(s) for s in (HERE/'round39/round-39-screen.jsonl').read_text().splitlines()]
positions={r['ply']:r for r in rows if r['type']=='position'}
plan={2:2000000,4:2000000,20:2000000,46:2000000,84:12000000}
out=HERE/'round39/focused-review.jsonl'
with chess.engine.SimpleEngine.popen_uci(str(EXE)) as e,out.open('x') as f:
    e.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
    def emit(r):f.write(json.dumps(r)+'\n');f.flush()
    emit(dict(type='plan',ply_nodes=plan,reference_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Preselected finite references, neither tablebase proof nor training/runtime lookup data'))
    for ply,nodes in plan.items():
        r=positions[ply];b=chess.Board(r['start_fen'])
        for u in r['history_uci']:b.push_uci(u)
        assert b.fen()==r['fen']
        best=reference(e,b,nodes);played=reference(e,b,nodes,[chess.Move.from_uci(r['played_uci'])])
        emit(dict(type='position',ply=ply,fen=b.fen(),san=r['san'],best=best,played=played,loss_cp=played['white_cp']-best['white_cp']))
        print(ply,r['san'],best['pv_uci'][:1],played['white_cp']-best['white_cp'],flush=True)
    emit(dict(type='complete'))
