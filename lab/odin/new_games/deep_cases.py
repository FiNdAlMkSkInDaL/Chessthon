"""Same-root reference comparisons, with bounds excluded and full PGN history."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from lab.odin.new_games.review_new import reference,sha
from lab.odin.development_review.review import pin_cpu4
import chess
import chess.engine

ap=argparse.ArgumentParser()
ap.add_argument('--round',type=int,required=True)
ap.add_argument('--cpu',type=int,required=True)
ap.add_argument('--nodes',type=int,default=2000000)
ap.add_argument('--odin',action='store_true')
ap.add_argument('--resume',action='store_true')
ap.add_argument('--selection',type=Path,default=HERE/'selected-roots.json')
ap.add_argument('--probes',type=Path,default=HERE/'odin-r10-probes.jsonl')
ap.add_argument('--output',type=Path)
args=ap.parse_args()
pin_cpu4(os.getpid(),args.cpu)
cases=[r for r in json.loads(args.selection.read_text(encoding='utf-8')) if r['round']==args.round]
probes=[]
if args.odin:
    probes=[json.loads(s) for s in args.probes.read_text(encoding='utf-8').splitlines()]
    assert probes[-1]['type']=='summary' and probes[-1]['verdict']=='PASS'
exe=Path('stockfish')
outpath=args.output or HERE/f"round-{args.round}-deep{'-odin' if args.odin else ''}.jsonl"
existing=[json.loads(s) for s in outpath.read_text(encoding='utf-8').splitlines()] if args.resume else []
if args.resume:
    assert existing[0]['selection_sha256']==sha(args.selection) and existing[0]['node_cap']==args.nodes
    assert existing[-1]['type']!='summary'
completed={r['id'] for r in existing if r['type']=='case'}
began=time.perf_counter()
with chess.engine.SimpleEngine.popen_uci(str(exe)) as engine,outpath.open('a' if args.resume else 'x',encoding='utf-8') as out:
    engine.configure({'Threads':1,'Hash':128,'UCI_ShowWDL':True})
    def emit(r):out.write(json.dumps(r,allow_nan=False)+'\n');out.flush()
    emit({'type':'resume_metadata' if args.resume else 'metadata','round':args.round,'engine_sha256':sha(exe),'script_sha256':sha(Path(__file__)),'reference_script_sha256':sha(HERE/'review_new.py'),'selection_sha256':sha(args.selection),
          'node_cap':args.nodes,'cpu':args.cpu,'method':'Independent cleared-hash same-root unrestricted and forced-move searches. Full PGN. Completed exact score iterations only. Finite reference is not ground truth; interpret differences with caution.'})
    for case in cases:
        if case['id'] in completed:continue
        board=chess.Board(case['start_fen'])
        for u in case['history_uci']:board.push_uci(u)
        assert board.fen()==case['fen'] and board.outcome(claim_draw=True) is None
        if args.odin:
            modes={r['mode']:r['uci'] for r in probes if r.get('id')==case['id']}
            assert len(modes)==2
            moves=sorted(set(modes.values())-{case['played_uci']})
            result={'alternatives':{u:reference(engine,board,args.nodes,[chess.Move.from_uci(u)]) for u in moves},'odin_modes':modes}
        else:
            result={'best':reference(engine,board,args.nodes),'played':reference(engine,board,args.nodes,[chess.Move.from_uci(case['played_uci'])])}
        emit(dict(type='case',id=case['id'],fen=board.fen(),storm_colour=case['storm_colour'],storm_move=case['played_uci'],**result))
        print(json.dumps({'id':case['id'],'seconds':time.perf_counter()-began}),flush=True)
    emit({'type':'summary','cases':len(cases),'seconds':time.perf_counter()-began})
