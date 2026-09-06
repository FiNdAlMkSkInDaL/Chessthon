"""Legality-aware SEE, EP identity and actual import signature regression."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import sys
import time


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--cpu',type=int,default=4)
    ap.add_argument('--native',action='store_true')
    args=ap.parse_args()
    import os
    if os.name=='nt':
        import ctypes
        kernel=ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype=ctypes.c_void_p
        kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
        assert kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(),1<<args.cpu)
    else:
        os.sched_setaffinity(0,{args.cpu})
    sys.path.insert(0,str(args.source.resolve()))
    import chess
    from board_nb import from_fen,move_uci
    from movegen_nb import generate_legal
    import search_nb
    import history
    report={'scope':'Supplemental SEE/EP/all-root/warmup checks','cases':[],
            'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    core=None
    if args.native:
        began=time.perf_counter()
        import agent
        import core_nb as core
        assert core.NUMBA_READY and core.root_search_nb.nopython_signatures
        report['cold_s']=time.perf_counter()-began
        signatures=[str(s) for s in core.root_search_nb.nopython_signatures]
    for fen,uci,expected in [
        ('5k2/6p1/8/8/8/8/1B6/4K1R1 w - - 0 1','g1g7',100),
        ('4k3/4b3/3p4/2B5/8/8/8/4R1K1 w - - 0 1','c5d6',100),
        ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1','e5d6',100)]:
        pos=from_fen(fen)
        m=next(m for m in generate_legal(pos) if move_uci(m)==uci)
        assert search_nb.see(pos,m)==expected
        if core:
            bb,mb,st=core.pack_pos(pos)
            copies=bb.copy(),mb.copy(),st.copy()
            assert core.see_nb(bb,mb,st,m)==expected
            import numpy as np
            assert all(np.array_equal(a,b) for a,b in zip(copies,(bb,mb,st)))
        report['cases'].append({'see':uci,'expected':expected})
    for fen in ['4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
                '4k3/8/8/r4pPK/8/8/8/8 w - f6 0 1',
                '4k3/8/8/3p4/8/8/8/4K3 w - d6 0 1']:
        board=chess.Board(fen)
        assert board.is_valid()
        pos=from_fen(fen)
        canonical=from_fen(board.fen(en_passant='legal'))
        assert pos.key==canonical.key
        if core:
            bb,mb,st=core.pack_pos(pos)
            assert bool(core.ep_hashable_nb(bb,mb,st))==board.has_legal_en_passant()
        report['cases'].append({'ep':fen,'legal':board.has_legal_en_passant()})
    board=chess.Board('2k5/4K3/6P1/8/4p3/5r1p/R7/8 b - - 5 83')
    legal=list(board.legal_moves)
    history.reset()
    history.observe_served(board)
    assert history.filter_root_moves(board,legal,True,deadline=0)==legal
    assert history.game_ply()==165 and not history.use_adjudication_eval()
    # Final-source helpers explicitly handle inputs outside their historical
    # >=99/nonterminal caller precondition. This is a strengthened release test.
    for clock in (0,5,98,99,100):
        for template in ('7k/7p/8/8/8/8/P7/K7 w - - {clock} 150',
                         '6k1/6p1/8/8/8/8/P4R2/6K1 w - - {clock} 150',
                         '8/8/8/8/8/k7/q7/K7 w - - {clock} 300'):
            board=chess.Board(template.format(clock=clock))
            assert board.is_valid()
            pos=from_fen(board.fen())
            moves=generate_legal(pos)
            expected=board.can_claim_fifty_moves()
            assert search_nb._fifty_claim_from_legal(pos,moves)==expected
            if core:
                bb,mb,st=core.pack_pos(pos)
                actual=core.fifty_claim_nb(bb,mb,st,np.array(moves,np.int32),len(moves),
                                          np.zeros(core.MAX_MOVES,np.int32),np.zeros(7,np.uint64))
                assert bool(actual)==expected
    report['total_fifty_cases']=15
    if core:
        pos=from_fen(chess.STARTING_FEN)
        root=generate_legal(pos)
        began=time.perf_counter()
        choice=core.search_root(pos,root,250.,250.,False,[pos.key])
        report['first_live_ms']=1000*(time.perf_counter()-began)
        assert choice in root and report['first_live_ms']<500
        assert signatures==[str(s) for s in core.root_search_nb.nopython_signatures]
    report['verdict']='PASS'
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
