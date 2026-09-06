"""Exact-source, real-clock site diagnostics; never part of release strength score."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))

ap=argparse.ArgumentParser()
ap.add_argument('--source',type=Path,default=ROOT/'odin_submission')
ap.add_argument('--cpu',type=int,default=4)
ap.add_argument('--roots',type=Path,default=HERE/'selected-roots.json')
ap.add_argument('--output',type=Path,default=HERE/'odin-r10-probes.jsonl')
args=ap.parse_args()
if os.name=='nt':
    from lab.odin.development_review.review import pin_cpu4
    pin_cpu4(os.getpid(),args.cpu)
else:
    os.sched_setaffinity(0,{args.cpu})
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
source=args.source.resolve()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob('*.py'))}
before=hashes()
sys.path.insert(0,str(source))
began=time.perf_counter()
import agent
import core_nb as core
import history
import chess
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
cold=time.perf_counter()-began
assert core.NUMBA_READY and core.root_search_nb.nopython_signatures
signatures=list(map(str,core.root_search_nb.nopython_signatures))
cases=json.loads(args.roots.read_text(encoding='utf-8'))
outpath=args.output
with outpath.open('x',encoding='utf-8') as out:
    def emit(r):out.write(json.dumps(r,default=str)+'\n');out.flush()
    emit({'type':'metadata','source':str(source.relative_to(ROOT)),'source_sha256':before,'cold_s':cold,'native_ready':True,'cpu':args.cpu,
          'python':platform.python_version(),'platform':platform.platform(),'machine':platform.machine(),
          'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'selection_sha256':hashlib.sha256(args.roots.read_bytes()).hexdigest(),
          'method':'Full PGN reconstructed. Agent history seeded only from historically served own turns and legal own moves, exactly the information available to its real process. Clean TT before each case/budget; no future-position leakage. Actual PGN clock for get_move; independent fixed 3 s root diagnostic also provided.',
          'limitations':'Host hardware can differ from the competition. Historical TT absent. Selected errors are diagnostic, not unbiased strength evidence.'})
    for case in cases:
        for mode in ('adaptive','fixed-3000ms'):
            for name in ('TT_KEY','TT_MOVE','TT_SCORE','TT_DEPTH','TT_GEN','HISTORY','KILLERS'):
                getattr(core,name).fill(0)
            core.TT_AGE[0]=1
            history.reset()
            board=chess.Board(case['start_fen'])
            own=case['storm_colour']=='white'
            for uci in case['history_uci']:
                if board.turn==own:
                    history.observe_served(board)
                    history.observe_our_uci(board,uci)
                board.push_uci(uci)
            assert board.fen()==case['fen'] and board.turn==own and board.outcome(claim_draw=True) is None
            if mode=='adaptive':
                began=time.perf_counter()
                uci=agent.get_move(case['fen'],case['time_left_ms'])
            else:
                history.observe_served(board)
                pos=from_fen(board.fen(en_passant='fen'))
                roots=generate_legal(pos)
                began=time.perf_counter()
                uci=move_uci(core.search_root(pos,roots,3000.,3000.,adjudicate=False,game_zkeys=history.zkeys().copy()))
            elapsed_ms=1000*(time.perf_counter()-began)
            assert chess.Move.from_uci(uci) in board.legal_moves
            info=core.last_info()
            r={'type':'probe','id':case['id'],'round':case['round'],'ply':case['ply'],'mode':mode,'uci':uci,'san':board.san(chess.Move.from_uci(uci)),
               'actual_wall_ms':elapsed_ms,'time_left_ms':case['time_left_ms'],'recorded_storm_uci':case['played_uci'],'recorded_storm_san':case['played_san'],
               'info':info,'history_keys':len(history.zkeys()),'adjudication_material_mode':history.use_adjudication_eval()}
            emit(r)
            print(json.dumps({k:r[k] for k in ('id','mode','san','actual_wall_ms')}),flush=True)
    assert hashes()==before and signatures==list(map(str,core.root_search_nb.nopython_signatures))
    emit({'type':'summary','verdict':'PASS','cases':len(cases),'probes':2*len(cases),'source_unchanged':True,'no_new_root_signature':True})
