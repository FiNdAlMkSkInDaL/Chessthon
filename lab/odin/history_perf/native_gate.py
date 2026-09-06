"""Native integration gate for the isolated history/TT experiment.

Run on the Linux signer under one core/2 GiB, with NUMBA_BOUNDSCHECK=1.
This is correctness evidence, not a playing-strength measurement.
"""
from __future__ import annotations
import argparse
import hashlib
import inspect
import itertools
import json
import os
from pathlib import Path
import platform
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == "linux" and platform.machine() == "x86_64"
    assert sys.version_info[:2] == (3, 12)
    assert len(os.sched_getaffinity(0)) == 1
    assert os.environ.get("NUMBA_BOUNDSCHECK") == "1", "Boundschecked run required"
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    started = time.perf_counter()
    import agent
    import core_nb as c
    import history
    import chess
    import numpy as np
    from board_nb import from_fen
    from movegen_nb import generate_legal, move_uci
    cold_s = time.perf_counter() - started
    assert c.NUMBA_READY and c.root_search_nb.nopython_signatures
    assert cold_s < 90, cold_s
    print(json.dumps({"event": "ready", "cold_s": cold_s}), flush=True)
    passed = []

    def clear():
        for name in ("TT_KEY", "TT_MOVE", "TT_SCORE", "TT_DEPTH", "TT_GEN", "HISTORY", "KILLERS"):
            getattr(c, name).fill(0)

    def signature(keys):
        result = c.HIST_SEED
        for key in keys:
            result = np.uint64(c.history_append(np.uint64(result), np.uint64(key)))
        return result

    def inputs(board, prior, depth=1, ply=0, context_tt=False):
        pos = from_fen(board.fen())
        bb, mb, st = c.pack_pos(pos)
        hist = np.zeros(len(prior) + c.MAX_PLY + 8, np.uint64)
        hist[:len(prior)] = prior
        return dict(bb=bb, mb=mb, st=st, depth=depth, alpha=-c.INF, beta=c.INF,
                    ply=ply, hist=hist, hlen=len(prior), adjudicate=int(not context_tt),
                    cap_left=max(0, 600 - board.ply()), has_pair=bool(c.history_has_pair(hist, len(prior))),
                    hist_sig=signature(prior), null_tree=False, max_nodes=10_000_000, allow_abort=False,
                    undos=np.zeros((c.MAX_PLY, 7), np.uint64),
                    stacks=np.zeros((c.MAX_PLY, c.MAX_MOVES), np.int32),
                    scratches=np.zeros((c.MAX_PLY, c.MAX_MOVES), np.int32),
                    ttk=c.TT_KEY, ttm=c.TT_MOVE, tts=c.TT_SCORE, ttd=c.TT_DEPTH,
                    ttg=c.TT_GEN, tta=c.TT_AGE, killers=c.KILLERS, histy=c.HISTORY,
                    nodes=np.zeros(2, np.int64), aborted=np.zeros(1, np.int32))

    def call(function, values):
        names = inspect.signature(function.py_func).parameters
        before = [values[n].copy() for n in ("bb", "mb", "st")]
        result = function(**{n: values[n] for n in names})
        for name, expected in zip(("bb", "mb", "st"), before):
            np.testing.assert_array_equal(values[name], expected)
        return result

    permutations = [11, 22, 11, 2**63 + 7]
    assert len({int(signature(p)) for p in itertools.permutations(permutations)}) == 1
    assert signature([11,11]) != signature([])
    assert signature([11,11,22]) != signature([11,22,22])
    passed.append("native multiplicity-sensitive order-independent digest")

    board = chess.Board("7k/6p1/8/8/8/8/P7/KR6 w - - 5 12")
    key = from_fen(board.fen()).key
    prior = [101, 202, 303]
    common = inputs(board, prior, context_tt=True)
    clear()
    expected = int(call(c.qsearch_nb, common))
    assert abs(expected) < 2000 and expected != 0
    for label, fifty, cap, keys in (
        ("rule50", 6, common["cap_left"], prior),
        ("cap", 5, common["cap_left"] - 1, prior),
        ("history counts", 5, common["cap_left"], [101,202,202]),
    ):
        clear()
        mismatch = c.score_tt_key(np.uint64(key), fifty, cap, signature(keys + [key]))
        c.tt_store(np.uint64(mismatch), 0, 20, c.EXACT, 7777, 0, c.TT_KEY, c.TT_MOVE,
                   c.TT_SCORE, c.TT_DEPTH, c.TT_GEN, c.TT_AGE)
        actual = int(call(c.qsearch_nb, inputs(board, prior, context_tt=True)))
        assert actual == expected, (label, actual, expected)
    clear()
    same = c.score_tt_key(np.uint64(key), 5, common["cap_left"], signature([303,101,202,key]))
    c.tt_store(np.uint64(same), 0, 20, c.EXACT, 7777, 0, c.TT_KEY, c.TT_MOVE,
               c.TT_SCORE, c.TT_DEPTH, c.TT_GEN, c.TT_AGE)
    assert int(call(c.qsearch_nb, inputs(board, prior, context_tt=True))) == 7777
    passed.append("actual qsearch rejects mismatched score contexts and accepts reordered identical counts")

    clear()
    move = generate_legal(from_fen(board.fen()))[0]
    c.move_hint_store(np.uint64(key), move, c.TT_KEY, c.TT_MOVE)
    assert c.probe_move(key) == move
    collision = np.uint64(key) ^ np.uint64(c.MOVE_HINT_SIZE)
    c.move_hint_store(collision, move + 1, c.TT_KEY, c.TT_MOVE)
    assert c.probe_move(key) == 0
    passed.append("board-only move hints validate full key and never expose score bounds")

    # A legal repeated sequence then pawn moves: compare exact draw claims and
    # full versus trimmed search after the old pair becomes unreachable.
    board = chess.Board()
    all_keys = [from_fen(board.fen()).key]
    for uci in ("g1f3", "g8f6", "f3g1", "f6g8", "e2e4", "e7e5",
                "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"):
        board.push_uci(uci)
        all_keys.append(from_fen(board.fen()).key)
        trimmed = history.reversible_root_keys(all_keys, board.halfmove_clock)
        if board.can_claim_threefold_repetition():
            clear()
            assert int(call(c.negamax_nb, inputs(board, trimmed))) == 0
        if board.halfmove_clock == 0:
            for fn in (c.qsearch_nb, c.negamax_nb):
                clear()
                full_values = inputs(board, all_keys[:-1])
                full_score = int(call(fn, full_values))
                np.testing.assert_array_equal(full_values["hist"][:len(all_keys)-1], all_keys[:-1])
                clear()
                trimmed_score = int(call(fn, inputs(board, [])))
                assert full_score == trimmed_score, (fn.py_func.__name__, full_score, trimmed_score)
    passed.append("native search matches referee claims and discards pre-zeroing pairs without undo corruption")

    # Force a legal zeroing child from a root which already has a repeated
    # board: its negated child value must match a history-free child search.
    board = chess.Board()
    prior = [from_fen(board.fen()).key]
    for uci in ("g1f3", "g8f6", "f3g1", "f6g8"):
        board.push_uci(uci)
        prior.append(from_fen(board.fen()).key)
    root = from_fen(board.fen())
    move = next(m for m in generate_legal(root) if move_uci(m) == "e2e4")
    values = inputs(board, prior[:-1], depth=2)
    values.update(root_moves=np.array([move], np.int32), nroot=1, pv=move,
                  root_work=np.zeros(1, np.int64))
    clear()
    actual_move, actual_score = call(c.root_search_nb, values)
    board.push_uci("e2e4")
    clear()
    child = inputs(board, [], depth=1, ply=1)
    expected_score = -int(call(c.negamax_nb, child))
    assert actual_move == move and actual_score == expected_score
    passed.append("legal root pawn transition resets inherited history context")

    board = chess.Board("3q3k/8/8/8/8/8/8/K2Q4 b - - 0 1")
    keys = [from_fen(board.fen()).key]
    for uci in ("h8g8", "a1b1", "g8g7", "b1a1", "g7h8", "a1b1", "h8g8",
                "b1b2", "g8h8", "b2a1", "h8h7", "a1a2", "h7g8", "a2a1", "g8h8"):
        board.push_uci(uci)
        assert board.is_valid() and board.outcome(claim_draw=True) is None
        keys.append(from_fen(board.fen()).key)
    values = inputs(board, keys[:-1], context_tt=True)
    undo = np.zeros(7, np.uint64)
    c.make_null(values["bb"], values["mb"], values["st"], undo)
    assert keys[:-1].count(int(values["st"][c.KEY])) == 2
    clear()
    # Deliberately feeding the synthetic board as real recreates the defect.
    assert call(c.qsearch_nb, values) == 0
    values["null_tree"] = True
    before_history = values["hist"].copy()
    clear()
    with_barrier = int(call(c.qsearch_nb, values))
    empty = dict(values)
    empty.update(hist=np.zeros(c.MAX_PLY + 8,np.uint64), hlen=0,
                 has_pair=False, hist_sig=c.HIST_SEED)
    clear()
    reference = int(call(c.qsearch_nb, empty))
    assert with_barrier == reference
    assert with_barrier != 0, "Fixture must expose removal of the fabricated draw"
    np.testing.assert_array_equal(values["hist"], before_history)
    assert not np.any(c.TT_KEY[:c.TT_SIZE]), "Null subtree stored a contextual score"
    passed.append("legal queen triangulation null subtree cannot claim a fictitious third occurrence")

    # The new view rebasing still fits a long caller's allocation, and the
    # cap precedes the search stack limit after the release audit repair.
    board = chess.Board("7k/6p1/8/8/8/8/P7/KR6 w - - 0 210")
    clear()
    long = inputs(board, list(range(1, 621)), depth=2)
    score = call(c.negamax_nb, long)
    assert score != 0
    np.testing.assert_array_equal(long["hist"][:620], list(range(1,621)))
    for fn in (c.qsearch_nb, c.negamax_nb):
        values = inputs(board, [], ply=c.MAX_PLY)
        values["cap_left"] = 0
        assert call(fn, values) == 0
    passed.append("boundschecked long-history rebasing and cap at maximum stack depth")

    report = {"status": "PASS", "cold_s": cold_s, "warmup_s": c.WARMUP_S,
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob("*.py")},
              "python": platform.python_version(), "machine": platform.machine(),
              "affinity": sorted(os.sched_getaffinity(0)), "boundschecked": True,
              "extra_move_hint_bytes": c.MOVE_HINT_SIZE * 12, "passed": passed,
              "limitations": "No match or Elo claim. Null search preserves existing real-edge cap/fifty policy but isolates repetition and contextual score TT throughout the synthetic subtree."}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
