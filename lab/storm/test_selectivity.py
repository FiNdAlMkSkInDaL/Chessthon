"""Storm selective-search gates and fixed-depth position benchmark.

Run with Python 3.12. --engine points at an unpacked engine, enabling the same
benchmark on v3 and Storm without silently mixing their module imports.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def buffers(c, np):
    return (
        np.zeros((c.MAX_PLY, 7), dtype=np.uint64),
        np.zeros((c.MAX_PLY, c.MAX_MOVES), dtype=np.int32),
        np.zeros((c.MAX_PLY, c.MAX_MOVES), dtype=np.int32),
        c.TT_KEY, c.TT_MOVE, c.TT_SCORE, c.TT_DEPTH, c.TT_GEN, c.TT_AGE,
        c.KILLERS, c.HISTORY,
        np.zeros(2, dtype=np.int64), np.zeros(1, dtype=np.int32),
    )


def clear_search(c):
    c.TT_KEY.fill(0)
    c.TT_MOVE.fill(0)
    c.TT_DEPTH.fill(0)
    c.TT_GEN.fill(0)
    c.HISTORY.fill(0)
    c.KILLERS.fill(0)


def run_position(c, np, fen, depth, limit=10**15):
    from board_nb import from_fen, move_uci
    from movegen_nb import generate_legal

    pos = from_fen(fen)
    bb, mb, st = c.pack_pos(pos)
    initial = (bb.copy(), mb.copy(), st.copy())
    root = np.array(generate_legal(pos), dtype=np.int32)
    hist = np.zeros(512, dtype=np.uint64)
    work = buffers(c, np)
    clear_search(c)
    pv, score = int(root[0]), 0
    start = time.perf_counter()
    for d in range(1, depth + 1):
        move, value = c.root_search_nb(
            bb, mb, st, root, len(root), d, hist, 0, pv,
            -c.INF, c.INF, 0, limit, *work,
        )
        assert all(np.array_equal(a, b) for a, b in zip(initial, (bb, mb, st))), (
            "search did not restore board", fen, d
        )
        if work[-1][0]:
            break
        pv, score = int(move), int(value)
    return {
        "fen": fen, "move": move_uci(pv), "score": score,
        "nodes": int(work[-2][0]), "seconds": time.perf_counter() - start,
        "aborted": bool(work[-1][0]),
    }


def test_history_relearns(c, np):
    h = np.zeros((12, 64), dtype=np.int32)
    for _ in range(200):
        c.history_update(h, 1, 18, 1600)
    assert 0 < h[1, 18] <= c.HISTORY_MAX
    for _ in range(20):
        c.history_update(h, 1, 18, -1600)
    assert -c.HISTORY_MAX <= h[1, 18] < 0, "history cannot unlearn a bad move"


def test_lmr_failhigh_requires_full_depth(c, np):
    """Exercise the real parent search with controlled child results.

    A late quiet looks like a cutoff at reduced depth, but loses at full depth.
    The parent must search it again and must not accept the false cutoff.
    """
    from board_nb import START_FEN, from_fen
    from movegen_nb import generate_legal

    clear_search(c)
    bb, mb, st = c.pack_pos(from_fen(START_FEN))
    initial = (bb.copy(), mb.copy(), st.copy())
    root = np.array(generate_legal(from_fen(START_FEN)), dtype=np.int32)
    c.sort_moves(mb, root, len(root), 0, 0, c.KILLERS, c.HISTORY)
    candidate = int(root[5])
    work = buffers(c, np)
    c.make_nb(bb, mb, st, candidate, work[0][0])
    candidate_key = int(st[c.KEY])
    c.unmake_nb(bb, mb, st, candidate, work[0][0])
    calls = []

    def child(bb, mb, st, depth, alpha, beta, *args):
        if int(st[c.KEY]) == candidate_key:
            calls.append((depth, alpha, beta))
            return -50 if depth < 3 else 5
        return 10

    parent = c.negamax_nb.py_func
    with patch.object(c, "negamax_nb", child), \
         patch.object(c, "RFP_MAX_D", 0), \
         patch.object(c, "NMP_MIN_D", 99), \
         patch.object(c, "IIR_MIN_D", 99):
        score = parent(
            bb, mb, st, 4, 0, 1, 0, np.zeros(512, dtype=np.uint64),
            0, False, 10**15, False, *work,
        )
    assert calls and calls[0][0] < 3 and calls[1][0] == 3, calls
    assert score < 1, ("unverified reduced cutoff", score)
    assert all(np.array_equal(a, b) for a, b in zip(initial, (bb, mb, st)))


def test_tactical_and_abort(c, np):
    import chess

    # Quiet mating move, then a capture mate previously endangered by SEE.
    cases = [
        "7k/5R2/6K1/8/8/8/8/8 w - - 0 1",
        "3r1bn1/4p1pr/2p1b3/1PP1k1Pp/p2pPp1P/1Q1P1P1B/1P1K1R2/R1B3N1 w - - 6 40",
        "7k/P7/8/8/8/8/8/K7 w - - 0 1",
        "8/5pk1/6p1/5P2/5KP1/8/8/8 w - - 0 1",
    ]
    for index, fen in enumerate(cases):
        result = run_position(c, np, fen, 4)
        board = chess.Board(fen)
        move = chess.Move.from_uci(result["move"])
        assert move in board.legal_moves, result
        if index < 2:
            board.push(move)
            assert board.is_checkmate(), result
        assert not result["aborted"], result
    # Abort even depth one, while fully unmaking the interrupted branch.
    result = run_position(c, np, cases[1], 4, limit=1)
    assert result["aborted"], result


def bench_fens(count):
    import chess.pgn

    found = []
    # Regularly spaced middlegame/endgame snapshots from every recorded game.
    # No engine labels or selected best moves influence this sample.
    games = sorted((ROOT / "Chess_results_day1").glob("*.pgn"))
    per_game = []
    for path in games:
        with path.open(encoding="utf-8-sig") as stream:
            game = chess.pgn.read_game(stream)
        samples = []
        if game:
            board = game.board()
            for ply, move in enumerate(game.mainline_moves(), 1):
                board.push(move)
                if ply in (16, 40, 72, 104, 136) and not board.is_game_over(claim_draw=True):
                    samples.append(board.fen())
        per_game.append(samples)
    for sample_index in range(5):
        for samples in per_game:
            if sample_index < len(samples) and samples[sample_index] not in found:
                found.append(samples[sample_index])
    return found[:count]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=Path, default=ROOT / "storm")
    parser.add_argument("--bench", action="store_true")
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cpu", type=int)
    args = parser.parse_args()
    if args.cpu is not None:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            kernel32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            ok = kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), 1 << args.cpu)
            assert ok, "unable to pin benchmark CPU"
        else:
            import os
            os.sched_setaffinity(0, {args.cpu})
    sys.path.insert(0, str(args.engine.resolve()))
    import numpy as np
    import core_nb as c

    start = time.perf_counter()
    # Use the live Python wrapper so compiled argument types match the agent.
    assert c.warmup() and c.NUMBA_READY
    print(f"warmup {time.perf_counter() - start:.3f}s", flush=True)
    if not args.bench:
        test_history_relearns(c, np)
        test_lmr_failhigh_requires_full_depth(c, np)
        test_tactical_and_abort(c, np)
        print("STORM SELECTIVITY OK", flush=True)
        return
    results = []
    for index, fen in enumerate(bench_fens(args.count), 1):
        result = run_position(c, np, fen, args.depth)
        results.append(result)
        print(index, result["move"], result["score"], result["nodes"],
              round(result["seconds"], 3), flush=True)
    report = {
        "engine": str(args.engine.resolve()), "depth": args.depth,
        "count": len(results), "nodes": sum(r["nodes"] for r in results),
        "seconds": sum(r["seconds"] for r in results), "positions": results,
        "note": "Windows local fixed-depth measurement; not an Elo estimate.",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "positions"}))


if __name__ == "__main__":
    main()
