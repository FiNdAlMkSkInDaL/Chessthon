"""Supplementary exact-source cold/warm signature gate; controller owns CPU envelope.

No readiness override. Run in a fresh constrained Linux Python3.12 process.
The existing exact-ZIP native gate still checks all protocol/perft/rule details.
"""
import argparse
import json
from pathlib import Path
import sys
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=args.source.resolve()
    sys.path.insert(0,str(source))
    began=time.perf_counter()
    import agent
    cold=time.perf_counter()-began
    import core_nb as core
    import numpy as np
    import chess
    from board_nb import from_fen,move_uci
    from movegen_nb import generate_legal
    assert Path(agent.__file__).resolve().is_relative_to(source)
    assert core.NUMBA_READY and core.root_search_nb.nopython_signatures
    assert cold<90,('cold import exceeded90s',cold)
    initial=[str(s) for s in core.root_search_nb.nopython_signatures]
    clock_initial=[str(s) for s in core.check_clock.nopython_signatures]
    assert clock_initial
    probes=[]
    for fen in (chess.STARTING_FEN,'8/8/8/8/8/k7/2q5/K7 b - - 0 300'):
        board=chess.Board(fen)
        pos=from_fen(fen)
        root=generate_legal(pos)
        began=time.perf_counter()
        choice=core.search_root(pos,root,250.,250.,[pos.key],board.ply())
        elapsed=1000*(time.perf_counter()-began)
        assert chess.Move.from_uci(move_uci(choice)) in board.legal_moves
        assert elapsed<500,('first live call deferred work',elapsed)
        assert [str(s) for s in core.root_search_nb.nopython_signatures]==initial,'A new root specialization compiled after import'
        assert [str(s) for s in core.check_clock.nopython_signatures]==clock_initial,'A new clock specialization compiled after import'
        probes.append({'fen':fen,'move':move_uci(choice),'elapsed_ms':elapsed})
    result={'verdict':'PASS','cold_agent_import_s':cold,'original_numba_ready':True,
            'root_signatures':initial,'clock_signatures':clock_initial,'live_calls':probes,
            'no_post_import_root_or_clock_specialization':True}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
