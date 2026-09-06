"""Fixed-depth deterministic search and deliberately colliding static-cache tests."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--cpu',type=int,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    import ctypes
    k=ctypes.windll.kernel32
    k.GetCurrentProcess.restype=ctypes.c_void_p
    k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    assert k.SetProcessAffinityMask(k.GetCurrentProcess(),1<<args.cpu)
    sys.path.insert(0,str(args.source.resolve()))
    began=time.perf_counter()
    import agent
    import core_nb as c
    import numpy as np
    import chess
    from board_nb import from_fen,move_uci
    from movegen_nb import generate_legal
    assert c.NUMBA_READY and c.root_search_nb.nopython_signatures
    report={'source':args.source.name,'cold_s':time.perf_counter()-began,'positions':[],
            'scope':'Windows fixed-depth diagnostic; identical node counts/moves/scores required before native timing or matches.'}
    cases=json.loads((ROOT/'lab/odin/development_review/fixed-r1-diagnostic-roots.json').read_text())
    fens=[r['fen'] for r in cases]+(ROOT/'lab/odin/release_openings/development.fen').read_text().splitlines()[4:8]
    for fen in fens:
        if not fen.strip() or fen.startswith('#'):continue
        pos=from_fen(fen)
        bb,mb,st=c.pack_pos(pos)
        root=np.array(generate_legal(pos),np.int32)
        for name in ('TT_KEY','TT_MOVE','TT_SCORE','TT_DEPTH','TT_GEN','KILLERS','HISTORY'):
            getattr(c,name).fill(0)
        c.TT_AGE[0]=1
        if hasattr(c,'evaluate_cached_nb'):
            index=c.TT_SIZE+int(st[c.KEY]&np.uint64(c.EVAL_CACHE_MASK))
            untouched=c.TT_KEY[:c.TT_SIZE].copy()
            expected=c.evaluate_nb(bb,st,0)
            for _ in range(2):
                assert c.evaluate_cached_nb(bb,st,0,c.TT_KEY,c.TT_SCORE,c.TT_DEPTH)==expected
            assert np.array_equal(untouched,c.TT_KEY[:c.TT_SIZE])
            # Force an index collision with a wrong full key and absurd value.
            c.TT_KEY[index]=st[c.KEY]^np.uint64(1<<32)
            c.TT_SCORE[index]=12345
            assert c.evaluate_cached_nb(bb,st,0,c.TT_KEY,c.TT_SCORE,c.TT_DEPTH)==expected
        nodes=np.zeros(2,np.int64);aborted=np.zeros(1,np.int32)
        began=time.perf_counter()
        choice,score=c.root_search_nb(bb,mb,st,root,len(root),7,
            np.empty(c.MAX_PLY+8,np.uint64),0,int(root[0]),-c.INF,c.INF,0,
            max(0,600-chess.Board(fen).ply()),10**15,
            np.zeros((c.MAX_PLY,7),np.uint64),np.zeros((c.MAX_PLY,c.MAX_MOVES),np.int32),
            np.zeros((c.MAX_PLY,c.MAX_MOVES),np.int32),c.TT_KEY,c.TT_MOVE,c.TT_SCORE,c.TT_DEPTH,
            c.TT_GEN,c.TT_AGE,c.KILLERS,c.HISTORY,nodes,aborted)
        elapsed=time.perf_counter()-began
        assert not aborted[0]
        report['positions'].append({'fen':fen,'move':move_uci(choice),'score':int(score),'nodes':int(nodes[0]),'seconds':elapsed})
        print(json.dumps(report['positions'][-1]),flush=True)
    report['verdict']='PASS'
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
