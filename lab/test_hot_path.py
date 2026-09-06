"""Signer-only regression gates for the actual Numba move/search path.

The ordinary perft suite validates the Python reference implementation.  A
freeze candidate must also prove that the separately-written Numba mirror is
both compiled and legal before its search results are trusted.
"""

from __future__ import annotations

import os
import time


def _require_runtime():
    try:
        import numpy as np
        import core_nb
    except ModuleNotFoundError as exc:
        if os.environ.get("HOT_PATH_REQUIRE") == "1":
            raise SystemExit(f"HOT PATH REQUIRED ({exc})") from exc
        print(f"HOT PATH SKIP ({exc})")
        return None, None
    return np, core_nb


def test_numba_perft(np, core_nb) -> None:
    from board_nb import from_fen
    from lab.perft import POSITIONS

    warmed = core_nb.warmup()
    if not warmed or not core_nb.NUMBA_READY:
        raise SystemExit(f"Numba warmup not ready ({core_nb.WARMUP_S:.2f}s)")
    target_s = float(getattr(core_nb, "WARMUP_TARGET_S", 50.0))
    if core_nb.WARMUP_S >= target_s:
        # Windows ARM is deliberately not a release target.  This opt-in only
        # lets it execute structural hot-path checks after a slow compile;
        # the signer still treats the target as a hard release failure.
        if os.environ.get("HOT_PATH_ALLOW_SLOW") != "1":
            raise SystemExit(
                f"Numba warmup {core_nb.WARMUP_S:.2f}s exceeds {target_s:.2f}s target"
            )
        print(f"HOT PATH local slow warmup accepted ({core_nb.WARMUP_S:.2f}s)")
    print(f"HOT PATH WARMUP {core_nb.WARMUP_S:.2f}s (target < {target_s:.2f}s)")
    for name, fen, expected in POSITIONS:
        depth = min(3, max(expected))
        got = core_nb.perft_pos(from_fen(fen), depth)
        want = expected[depth]
        if got != want:
            raise SystemExit(f"Numba perft {name} d{depth}: got {got}, want {want}")


def test_tempo_rewards_side_to_move(np, core_nb) -> None:
    """A symmetric position must give the tempo bonus to either mover."""
    from board_nb import from_fen
    from eval_nb import TEMPO, pesto

    for side in ("w", "b"):
        pos = from_fen(f"4k3/8/8/8/8/8/8/4K3 {side} - - 0 1")
        without_tempo = pesto(pos, tempo=False)
        with_tempo = pesto(pos, tempo=True)
        if without_tempo != 0 or with_tempo != TEMPO:
            raise SystemExit(
                f"Python tempo perspective {side}: base={without_tempo}, "
                f"with={with_tempo}, want 0/{TEMPO}"
            )
        bb, _mb, st = core_nb.pack_pos(pos)
        nb_without = int(core_nb.pesto_nb(bb, st, False))
        nb_with = int(core_nb.pesto_nb(bb, st, True))
        if nb_without != 0 or nb_with != TEMPO:
            raise SystemExit(
                f"Numba tempo perspective {side}: base={nb_without}, "
                f"with={nb_with}, want 0/{TEMPO}"
            )


def _numba_qsearch(np, core_nb, pos) -> int:
    bb, mb, st = core_nb.pack_pos(pos)
    core_nb.TT_KEY.fill(0)
    core_nb.TT_MOVE.fill(0)
    core_nb.TT_SCORE.fill(0)
    core_nb.TT_DEPTH.fill(0)
    core_nb.TT_GEN.fill(0)
    hist = np.empty(512, dtype=np.uint64)
    undos = np.zeros((core_nb.MAX_PLY, 7), dtype=np.uint64)
    stacks = np.zeros((core_nb.MAX_PLY, core_nb.MAX_MOVES), dtype=np.int32)
    scratches = np.zeros((core_nb.MAX_PLY, core_nb.MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(1, dtype=np.int64)
    aborted = np.zeros(1, dtype=np.int32)
    return int(
        core_nb.qsearch_nb(
            bb,
            mb,
            st,
            -core_nb.INF,
            core_nb.INF,
            0,
            hist,
            0,
            0,
            10**15,
            False,
            undos,
            stacks,
            scratches,
            core_nb.TT_KEY,
            core_nb.TT_MOVE,
            core_nb.TT_SCORE,
            core_nb.TT_DEPTH,
            core_nb.TT_GEN,
            core_nb.TT_AGE,
            core_nb.KILLERS,
            core_nb.HISTORY,
            nodes,
            aborted,
        )
    )


def _numba_negamax(np, core_nb, pos, depth: int, alpha: int, beta: int) -> int:
    bb, mb, st = core_nb.pack_pos(pos)
    core_nb.TT_KEY.fill(0)
    core_nb.TT_MOVE.fill(0)
    core_nb.TT_SCORE.fill(0)
    core_nb.TT_DEPTH.fill(0)
    core_nb.TT_GEN.fill(0)
    hist = np.empty(512, dtype=np.uint64)
    undos = np.zeros((core_nb.MAX_PLY, 7), dtype=np.uint64)
    stacks = np.zeros((core_nb.MAX_PLY, core_nb.MAX_MOVES), dtype=np.int32)
    scratches = np.zeros((core_nb.MAX_PLY, core_nb.MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(1, dtype=np.int64)
    aborted = np.zeros(1, dtype=np.int32)
    return int(
        core_nb.negamax_nb(
            bb,
            mb,
            st,
            depth,
            alpha,
            beta,
            0,
            hist,
            0,
            0,
            10**15,
            False,
            undos,
            stacks,
            scratches,
            core_nb.TT_KEY,
            core_nb.TT_MOVE,
            core_nb.TT_SCORE,
            core_nb.TT_DEPTH,
            core_nb.TT_GEN,
            core_nb.TT_AGE,
            core_nb.KILLERS,
            core_nb.HISTORY,
            nodes,
            aborted,
        )
    )


def test_terminal_draw_contract(np, core_nb) -> None:
    """Search terminals mirror the referee before static evaluation or TT."""
    import chess

    from board_nb import from_fen
    from eval_nb import insufficient_material
    from search_nb import MATE, qsearch_score
    from tt_nb import tt

    material_cases = (
        "7k/8/8/8/8/8/8/K7 w - - 0 1",  # K v K
        "7k/8/8/8/8/8/8/K1B5 w - - 0 1",  # KB v K
        "7k/8/8/8/8/8/8/K1N5 w - - 0 1",  # KN v K
        "7k/8/8/8/5b2/8/8/K1B5 w - - 0 1",  # same-colour bishops
        "7k/8/8/8/4b3/8/8/K1B5 w - - 0 1",  # opposite bishops
        "7k/8/8/8/8/8/8/K1NN4 w - - 0 1",  # KNN v K
        "7k/8/8/8/8/8/P7/K7 w - - 0 1",  # pawn
        "7k/8/8/8/8/8/8/K1R5 w - - 0 1",  # rook
        "7k/8/8/8/8/8/5n2/K1N5 w - - 0 1",  # KN v KN
    )
    for fen in material_cases:
        expected = chess.Board(fen).is_insufficient_material()
        pos = from_fen(fen)
        py = insufficient_material(pos)
        bb, _mb, _st = core_nb.pack_pos(pos)
        nb = bool(core_nb.insufficient_material_nb(bb))
        if py != expected or nb != expected:
            raise SystemExit(
                f"insufficient material mismatch {fen}: python={py} numba={nb} "
                f"referee={expected}"
            )

    cases = (
        ("stalemate", "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", 0),
        ("claim at 99", "7k/8/8/8/8/8/8/K6R w - - 99 1", 0),
        ("mate before rule 50", "7k/6Q1/5K2/8/8/8/P7/8 b - - 100 1", -MATE),
    )
    for name, fen, expected in cases:
        pos = from_fen(fen)
        tt.clear()
        py = qsearch_score(pos)
        nb = _numba_qsearch(np, core_nb, pos)
        if py != expected or nb != expected:
            raise SystemExit(
                f"{name}: python={py} numba={nb}, want {expected}"
            )

    # At 99, a position whose only legal move is a capture is not yet
    # claimable; search must cross the zeroing move instead of stopping at 0.
    zeroing_only = from_fen("8/8/8/8/8/8/r6P/K1k5 w - - 99 1")
    tt.clear()
    py = qsearch_score(zeroing_only)
    nb = _numba_qsearch(np, core_nb, zeroing_only)
    if py <= 0 or nb <= 0:
        raise SystemExit(f"rule-50 zeroing continuation: python={py} numba={nb}")


def test_checks_are_never_forward_pruned(np, core_nb) -> None:
    """Approximate SEE/futility must not hide checking moves or mates."""
    from board_nb import from_fen
    from search_nb import MATE

    capture_mate = from_fen(
        "3r1bn1/4p1pr/2p1b3/1PP1k1Pp/p2pPp1P/1Q1P1P1B/1P1K1R2/R1B3N1 w - - 6 40"
    )
    score = _numba_qsearch(np, core_nb, capture_mate)
    if score < MATE - 8:
        raise SystemExit(f"SEE pruned checking capture mate: score={score}")

    quiet_mate = from_fen("7k/5R2/6K1/8/8/8/8/8 w - - 0 1")
    score = _numba_negamax(np, core_nb, quiet_mate, 1, 1000, 1001)
    if score <= 1000:
        raise SystemExit(f"forward futility pruned quiet mate: score={score}")


def test_queen_promotion_is_ordered_first(np, core_nb) -> None:
    from board_nb import from_fen
    from movegen_nb import generate_legal, move_uci

    pos = from_fen("7k/P7/8/8/8/8/8/K7 w - - 0 1")
    expected = ["a7a8q", "a7a8r", "a7a8b", "a7a8n"]
    py = [move_uci(move) for move in generate_legal(pos) if move_uci(move).startswith("a7a8")]
    if py != expected:
        raise SystemExit(f"Python promotion order {py}, want {expected}")

    bb, mb, st = core_nb.pack_pos(pos)
    out = np.zeros(core_nb.MAX_MOVES, dtype=np.int32)
    scratch = np.zeros(core_nb.MAX_MOVES, dtype=np.int32)
    n = int(core_nb.gen_legal(bb, mb, st, out, scratch))
    nb = [move_uci(int(out[i])) for i in range(n) if move_uci(int(out[i])).startswith("a7a8")]
    if nb != expected:
        raise SystemExit(f"Numba promotion order {nb}, want {expected}")


def test_all_pruned_node_returns_fail_low(np, core_nb) -> None:
    """All-quiet king position exercises the forward-futility empty-loop path."""
    from board_nb import from_fen

    pos = from_fen("4k3/8/8/8/8/8/P7/4K3 w - - 0 1")
    bb, mb, st = core_nb.pack_pos(pos)
    core_nb.TT_KEY.fill(0)
    core_nb.TT_MOVE.fill(0)
    core_nb.TT_SCORE.fill(0)
    core_nb.TT_DEPTH.fill(0)
    core_nb.TT_GEN.fill(0)
    hist = np.empty(512, dtype=np.uint64)
    undos = np.zeros((core_nb.MAX_PLY, 7), dtype=np.uint64)
    stacks = np.zeros((core_nb.MAX_PLY, core_nb.MAX_MOVES), dtype=np.int32)
    scratches = np.zeros((core_nb.MAX_PLY, core_nb.MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(1, dtype=np.int64)
    aborted = np.zeros(1, dtype=np.int32)
    alpha = 10_000
    score = core_nb.negamax_nb(
        bb,
        mb,
        st,
        1,
        alpha,
        alpha + 1,
        0,
        hist,
        0,
        0,
        10**15,
        False,
        undos,
        stacks,
        scratches,
        core_nb.TT_KEY,
        core_nb.TT_MOVE,
        core_nb.TT_SCORE,
        core_nb.TT_DEPTH,
        core_nb.TT_GEN,
        core_nb.TT_AGE,
        core_nb.KILLERS,
        core_nb.HISTORY,
        nodes,
        aborted,
    )
    if score != alpha:
        raise SystemExit(f"all-pruned node returned {score}, want fail-low {alpha}")
    index = int(st[core_nb.KEY]) & core_nb.TT_MASK
    if core_nb.TT_KEY[index] != 0:
        raise SystemExit("all-pruned node wrote a synthetic TT bound")


def test_tiny_hard_budget_keeps_legal_fallback(np, core_nb) -> None:
    """A sub-iteration budget must not enter the unabortable depth-one pass."""
    from board_nb import START_FEN, from_fen
    from movegen_nb import generate_legal
    from time_nb import MIN_ITER_MS

    pos = from_fen(START_FEN)
    root = generate_legal(pos)
    _ = core_nb.search_root(
        pos, root, float(MIN_ITER_MS - 1), 0.0, False, []
    )
    if core_nb.last_nodes() != 0:
        raise SystemExit("sub-iteration budget started a depth-one search")


def test_warmup_covers_a_tactical_root(np, core_nb) -> None:
    """A capture-rich first move must not JIT on the match clock."""
    from board_nb import from_fen, move_uci
    from movegen_nb import generate_legal
    from time_nb import MIN_ITER_MS

    pos = from_fen("q4rk1/2Nbppbp/p2p1np1/8/Q1Pp4/3P2P1/PP2PP1P/R1B2RK1 b - - 1 13")
    started = time.perf_counter()
    move = core_nb.search_root(
        pos,
        generate_legal(pos),
        float(MIN_ITER_MS + 50),
        0.0,
        False,
        [],
    )
    elapsed = time.perf_counter() - started
    if not move_uci(move):
        raise SystemExit("tactical-root smoke returned no move")
    # The release host should execute this bounded root pass, not compile it.
    # Windows ARM may be arbitrarily slow and is structural-only.
    if elapsed > 2.0 and os.environ.get("HOT_PATH_ALLOW_SLOW") != "1":
        raise SystemExit(f"tactical root remained cold ({elapsed:.2f}s)")
    if elapsed > 2.0:
        print(f"HOT PATH local slow tactical root accepted ({elapsed:.2f}s)")


def main() -> None:
    np, core_nb = _require_runtime()
    if core_nb is None:
        return
    from lab.test_iteration_start import test_python_fallback_keeps_the_seeded_legal_move

    test_numba_perft(np, core_nb)
    test_tempo_rewards_side_to_move(np, core_nb)
    test_terminal_draw_contract(np, core_nb)
    test_checks_are_never_forward_pruned(np, core_nb)
    test_queen_promotion_is_ordered_first(np, core_nb)
    test_all_pruned_node_returns_fail_low(np, core_nb)
    test_tiny_hard_budget_keeps_legal_fallback(np, core_nb)
    test_warmup_covers_a_tactical_root(np, core_nb)
    test_python_fallback_keeps_the_seeded_legal_move()
    print("HOT PATH OK")


if __name__ == "__main__":
    main()
