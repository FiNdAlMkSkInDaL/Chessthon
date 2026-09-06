"""Windows CPU4 development-only comparison at exact full-history roots."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from lab.odin.development_review.review import pin_cpu4

THREADS=('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS',
         'NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')


def hashes(source):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob('*.py'))}


def worker(args):
    import ctypes
    k=ctypes.windll.kernel32
    k.GetCurrentProcess.restype=ctypes.c_void_p
    k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    assert k.SetProcessAffinityMask(k.GetCurrentProcess(),1<<args.cpu)
    source=args.source.resolve()
    before=hashes(source)
    sys.path.insert(0,str(source))
    started=time.perf_counter()
    import agent
    cold_s=time.perf_counter()-started
    import core_nb as core
    import numpy as np
    import chess
    from board_nb import from_fen,move_uci
    from movegen_nb import generate_legal
    assert Path(agent.__file__).resolve().is_relative_to(source)
    assert Path(core.__file__).resolve().is_relative_to(source)
    assert core.NUMBA_READY, ('Original native readiness is false',cold_s,core.WARMUP_S)
    initially_warmed=bool(core.root_search_nb.nopython_signatures)
    print(json.dumps({'source':source.name,'cold_s':cold_s,'warmup_s':core.WARMUP_S,
                      'original_numba_ready':True,'root_signature_present_after_import':initially_warmed}),flush=True)
    deferred_compile_s=0.0
    if not initially_warmed:
        # Windows can spend the tiny import warmup budget compiling preparatory
        # helpers and never enter the root. Measure a separate diagnostic compile
        # without altering source/readiness; exclude it from timed chess results.
        initial=from_fen(chess.STARTING_FEN)
        began=time.perf_counter()
        core.search_root(initial,generate_legal(initial),120000.0,0.0,[initial.key],0)
        deferred_compile_s=time.perf_counter()-began
        print(json.dumps({'source':source.name,'off_clock_diagnostic_compile_s':deferred_compile_s}),flush=True)
    assert core.root_search_nb.nopython_signatures
    assert core.NUMBA_READY
    rows=json.loads(args.roots.read_text())
    wanted=[r for r in rows if r['id'].endswith(('ply42','ply44'))]
    assert len(wanted)==2
    results=[]
    for case in wanted:
        board=chess.Board(case['start_fen'])
        keys=[from_fen(board.fen(en_passant='fen')).key]
        for uci in case['history_uci']:
            board.push_uci(uci)
            keys.append(from_fen(board.fen(en_passant='fen')).key)
        assert board.is_valid() and board.fen()==case['fen'] and board.outcome(claim_draw=True) is None
        for budget in (1000,3000):
            for name in ('TT_KEY','TT_MOVE','TT_SCORE','TT_DEPTH','TT_GEN','HISTORY','KILLERS'):
                getattr(core,name).fill(0)
            core.TT_AGE[0]=1
            pos=from_fen(board.fen(en_passant='fen'))
            root=generate_legal(pos)
            assert {move_uci(m) for m in root}=={m.uci() for m in board.legal_moves}
            began=time.perf_counter()
            kwargs={'game_zkeys':keys.copy()}
            if 'absolute_ply' in inspect.signature(core.search_root).parameters:
                kwargs['absolute_ply']=board.ply()
            else:
                kwargs['adjudicate']=False
            best=core.search_root(pos,root,float(budget),float(budget),**kwargs)
            elapsed_ms=1000*(time.perf_counter()-began)
            uci=move_uci(best)
            assert chess.Move.from_uci(uci) in board.legal_moves
            info=core.last_info()
            result={'id':case['id'],'fen':board.fen(),'history_uci':case['history_uci'],
                    'full_recorded_keys':len(keys),'absolute_ply':board.ply(),
                    'hard_ms':budget,'soft_ms':budget,'actual_wall_ms':elapsed_ms,
                    'move':uci,'san':board.san(chess.Move.from_uci(uci)),
                    'depth':info.get('depth'),'score':info.get('score'),'nodes':info.get('nodes'),
                    'info':info,'original_recorded_move':case['played_uci']}
            results.append(result)
            print(json.dumps({k:result[k] for k in ('id','hard_ms','actual_wall_ms','san','depth','score','nodes')}),flush=True)
    assert hashes(source)==before,'Source changed during comparison'
    report={'verdict':'PASS','source':source.name,'source_sha256':before,
            'runtime':{'python':platform.python_version(),'platform':platform.platform(),'machine':platform.machine(),
                       'packages':{p:importlib.metadata.version(p) for p in ('chess','numpy','numba','llvmlite')}},
            'cpu':args.cpu,'thread_env':{name:os.environ.get(name) for name in THREADS},
            'cold_agent_import_s':cold_s,'warmup_s':core.WARMUP_S,'original_numba_ready':True,
            'root_signature_present_after_import':initially_warmed,
            'off_clock_diagnostic_compile_s':deferred_compile_s,
            'source_unchanged':True,'results':results,
            'method':'Fresh process per source; all full-history roots legal; TT including move hints, scores, history and killers reset before each budget/root; soft and hard targets both equal stated budget; real adaptive controller may finish earlier.',
            'limitations':['Windows laptop diagnosis only; not Linux timing or playing-strength evidence.',
                           'Two selected development positions are not holdout cases.',
                           'One run per root/budget/source; timing can change iteration completion.']}
    args.output.write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--cpu',type=int,default=4)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--roots',type=Path,default=HERE/'fixed-r1-diagnostic-roots.json')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--tag',default='offclockwarm')
    args=parser.parse_args()
    if args.worker:
        worker(args)
        return
    env=os.environ.copy()
    env.update({key:'1' for key in THREADS})
    env['PYTHONDONTWRITEBYTECODE']='1'
    for source_name in ('odin_history_perf','odin_compact_guard'):
        output=HERE/(source_name+'-critical-roots-windows-'+args.tag+'.json')
        if output.exists():
            raise SystemExit('Refusing to replace prior diagnostic evidence: '+str(output))
        command=[sys.executable,'-B','-u',str(Path(__file__).resolve()),'--worker',
                 '--source',str(ROOT/source_name),'--roots',str(args.roots),'--output',str(output)]
        try:
            completed=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180)
            (HERE/(source_name+'-critical-roots-windows-'+args.tag+'.stdout.txt')).write_text(completed.stdout,encoding='utf-8')
            (HERE/(source_name+'-critical-roots-windows-'+args.tag+'.stderr.txt')).write_text(completed.stderr,encoding='utf-8')
            print(completed.stdout,end='',flush=True)
            if completed.returncode:
                raise SystemExit(source_name+' failed: '+completed.stderr[-2000:])
        except subprocess.TimeoutExpired as exc:
            raise SystemExit(source_name+' exceeded180-second worker timeout') from exc


if __name__=='__main__':
    main()
