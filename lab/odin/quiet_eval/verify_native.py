"""Compare native features against independent python-chess geometry on all labels."""
import argparse
import json
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    import ctypes
    k=ctypes.windll.kernel32
    k.GetCurrentProcess.restype=ctypes.c_void_p
    k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    assert k.SetProcessAffinityMask(k.GetCurrentProcess(),1<<5)
    sys.path.insert(0,str(ROOT))
    sys.path.insert(0,str(args.source.resolve()))
    import core_nb as core
    from board_nb import from_fen
    from lab.odin.quiet_eval.expanded_fit import extract
    import chess
    import numpy as np
    from numba import njit
    rows=[json.loads(s) for s in (HERE/'fit-records.jsonl').read_text().splitlines()]
    n=0
    for row in rows:
        board=chess.Board(row['fen'])
        for b in (board,board.mirror()):
            bb,mb,st=core.pack_pos(from_fen(b.fen()))
            expected=extract(b)
            actual=core.positional_features_nb(bb,st)
            assert tuple(actual)==expected,(b.fen(),expected,actual.tolist())
            phase=min(24,int(st[core.PHASE_ACC]))
            correction=round((sum(int(a)*int(v) for a,v in zip(actual,core.FEATURE_MG))*phase+
                              sum(int(a)*int(v) for a,v in zip(actual,core.FEATURE_EG))*(24-phase))/24)
            assert core.positional_correction_nb(bb,st)==max(-400,min(400,correction))
            n+=1
    @njit
    def bench(bb,st,iterations,expanded):
        result=0
        for i in range(iterations):
            st[core.SIDE]=np.uint64(i&1)
            result += core.evaluate_nb(bb,st,0) if expanded else core.pesto_nb(bb,st,True)
        return result
    bb,mb,st=core.pack_pos(from_fen(chess.STARTING_FEN))
    bench(bb,st,1,False)
    timings={}
    for expanded in (False,True):
        began=time.perf_counter()
        bench(bb,st,100000,expanded)
        timings[str(expanded)]=(time.perf_counter()-began)*10000
    report={'verdict':'PASS','feature_and_correction_cases':n,'eval_nanoseconds_per_call':timings,
            'limitations':'Laptop timing diagnostic only; not search throughput or native signer readiness.'}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
