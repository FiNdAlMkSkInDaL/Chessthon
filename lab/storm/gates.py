"""Structural and real-clock gates for Storm's exact staged source."""
from pathlib import Path
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(os.environ.get("STORM_SOURCE", ROOT / "storm"))))
import chess
import numpy as np
import core_nb as c
from board_nb import from_fen, move_uci
from movegen_nb import generate_legal


def main():
    began = time.perf_counter()
    assert c.warmup() and c.NUMBA_READY
    print(f"STORM WARMUP {c.WARMUP_S:.3f}s", flush=True)
    from lab.test_hot_path import (
        test_tempo_rewards_side_to_move, test_terminal_draw_contract,
        test_checks_are_never_forward_pruned, test_queen_promotion_is_ordered_first,
        test_all_pruned_node_returns_fail_low,
    )
    from lab.perft import POSITIONS
    for name, fen, expected in POSITIONS:
        d = min(3, max(expected))
        assert c.perft_pos(from_fen(fen), d) == expected[d], name
    print("STORM PERFT PASS", flush=True)
    for test in (test_tempo_rewards_side_to_move, test_terminal_draw_contract,
                 test_checks_are_never_forward_pruned, test_queen_promotion_is_ordered_first,
                 test_all_pruned_node_returns_fail_low):
        test(np, c)
    print("STORM SEARCH CONTRACT PASS", flush=True)
    from lab.storm.test_accumulators import main as accumulators
    accumulators()
    roots = [chess.STARTING_FEN,
             "q4rk1/2Nbppbp/p2p1np1/8/Q1Pp4/3P2P1/PP2PP1P/R1B2RK1 b - - 1 13",
             "r3qrk1/ppp3bp/3p2p1/2nP2B1/2P1N1b1/5P2/PPQ1BP2/R3K2R w KQ - 0 16",
             "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
             "4k3/P7/8/8/8/8/7p/4K3 w - - 0 1"]
    for hard in (30., 100., 300.):
        for fen in roots:
            pos=from_fen(fen)
            c.TT_KEY.fill(0)
            started=time.perf_counter()
            move=c.search_root(pos,generate_legal(pos),hard,hard,False,[])
            elapsed=(time.perf_counter()-started)*1000
            assert chess.Move.from_uci(move_uci(move)) in chess.Board(fen).legal_moves
            assert elapsed <= hard+200, ("deadline overrun", hard, elapsed, fen)
    # Artificial expiry exercises interruption inside even a depth-one pass.
    nodes=np.array([1024, time.perf_counter_ns()-1],dtype=np.int64)
    aborted=np.zeros(1,dtype=np.int32)
    assert c.check_clock(nodes,10**15,True,aborted) and aborted[0]
    print("STORM REAL DEADLINE PASS", flush=True)
    import agent
    for clock_ms in (100, 450, 1000):
        for fen in roots:
            started=time.perf_counter()
            move=agent.get_move(fen,clock_ms)
            elapsed=(time.perf_counter()-started)*1000
            assert chess.Move.from_uci(move) in chess.Board(fen).legal_moves
            assert elapsed < clock_ms, (clock_ms, elapsed)
    print(f"STORM GATES PASS elapsed={time.perf_counter()-began:.3f}s", flush=True)


if __name__ == "__main__":
    main()
