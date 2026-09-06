"""Perft oracle (python-chess) plus Brick A ray-loop engine vs that oracle."""

from __future__ import annotations

import random

import chess

from board_nb import compute_key, from_fen, make, to_fen, unmake
from movegen_nb import divide, generate_legal, legal_uci, move_uci, perft as engine_perft

# CPW / standard suite. Engine must match these, not only the python-chess walk.
POSITIONS: tuple[tuple[str, str, dict[int, int]], ...] = (
    (
        "startpos",
        chess.STARTING_FEN,
        {1: 20, 2: 400, 3: 8902, 4: 197_281, 5: 4_865_609},
    ),
    (
        "kiwipete",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        {1: 48, 2: 2039, 3: 97_862, 4: 4_085_603},
    ),
    (
        "cpw3",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        {1: 14, 2: 191, 3: 2812, 4: 43_238, 5: 674_624},
    ),
    (
        "cpw4",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
        {1: 6, 2: 264, 3: 9467, 4: 422_333},
    ),
    (
        "cpw5",
        "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
        {1: 44, 2: 1486, 3: 62_379, 4: 2_103_487},
    ),
    (
        "cpw6",
        "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
        {1: 46, 2: 2079, 3: 89_890, 4: 3_894_594},
    ),
)


def oracle_perft(board: chess.Board, depth: int) -> int:
    if depth == 0:
        return 1
    nodes = 0
    for move in board.legal_moves:
        board.push(move)
        nodes += oracle_perft(board, depth - 1)
        board.pop()
    return nodes


def _dump_divide(fen: str, depth: int) -> str:
    pos = from_fen(fen)
    board = chess.Board(fen)
    ours = dict(divide(pos, depth))
    ref: dict[str, int] = {}
    for move in board.legal_moves:
        uci = move.uci()
        board.push(move)
        ref[uci] = oracle_perft(board, depth - 1) if depth > 1 else 1
        board.pop()
    keys = sorted(set(ours) | set(ref))
    lines = []
    for k in keys:
        o, r = ours.get(k), ref.get(k)
        mark = "" if o == r else "  <<<"
        lines.append(f"  {k}: engine={o} ref={r}{mark}")
    extra = sorted(set(ours) - set(ref))
    missing = sorted(set(ref) - set(ours))
    if extra:
        lines.append(f"  extra: {extra}")
    if missing:
        lines.append(f"  missing: {missing}")
    return "\n".join(lines)


def check_oracle(max_depth: int = 3) -> list[str]:
    failures: list[str] = []
    for name, fen, expected in POSITIONS:
        board = chess.Board(fen)
        for depth, want in expected.items():
            if depth > max_depth:
                continue
            got = oracle_perft(board, depth)
            if got != want:
                failures.append(f"oracle {name} depth {depth}: got {got} want {want}")
    return failures


def check_fen_roundtrip(fens: list[str]) -> list[str]:
    failures: list[str] = []
    for fen in fens:
        board = chess.Board(fen)
        want = board.fen(en_passant="fen")
        pos = from_fen(want)
        got = to_fen(pos)
        if got != want:
            failures.append(f"fen roundtrip: got {got!r} want {want!r}")
    return failures


def check_legal_sets(fens: list[str]) -> list[str]:
    failures: list[str] = []
    for fen in fens:
        board = chess.Board(fen)
        ref = {m.uci() for m in board.legal_moves}
        ours = legal_uci(from_fen(fen))
        if ours != ref:
            extra = sorted(ours - ref)
            missing = sorted(ref - ours)
            failures.append(
                f"legal {fen}: extra={extra[:12]} missing={missing[:12]}"
            )
    return failures


def check_make_unmake(fens: list[str]) -> list[str]:
    failures: list[str] = []
    for fen in fens:
        pos = from_fen(fen)
        snap = pos.snapshot()
        for move in generate_legal(pos):
            undo = make(pos, move)
            if pos.key != compute_key(pos):
                failures.append(
                    f"hash after make {fen} {move}: key={pos.key} recomputed={compute_key(pos)}"
                )
                unmake(pos, move, undo)
                break
            unmake(pos, move, undo)
            if pos.snapshot() != snap:
                failures.append(f"unmake restore failed: {fen}")
                break
        if len(failures) > 8:
            break
    return failures


def check_fen_after_make(fens: list[str], plies: int = 1) -> list[str]:
    failures: list[str] = []

    def rec(pos, board: chess.Board, depth: int, root: str) -> None:
        if depth == 0 or failures:
            return
        for move in generate_legal(pos):
            uci = move_uci(move)
            undo = make(pos, move)
            board.push_uci(uci)
            got = to_fen(pos)
            want = board.fen(en_passant="fen")
            if got != want:
                failures.append(f"fen-after-make {root} {uci}: got {got!r} want {want!r}")
                board.pop()
                unmake(pos, move, undo)
                return
            rec(pos, board, depth - 1, root)
            board.pop()
            unmake(pos, move, undo)
            if failures:
                return

    for fen in fens:
        rec(from_fen(fen), chess.Board(fen), plies, fen)
        if len(failures) > 6:
            break
    return failures


def check_unmake_walk(fen: str, plies: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    pos = from_fen(fen)
    start = pos.snapshot()
    stack: list[tuple[int, object]] = []
    for _ in range(plies):
        moves = generate_legal(pos)
        if not moves:
            break
        move = rng.choice(moves)
        stack.append((move, make(pos, move)))
        if pos.key != compute_key(pos):
            return [f"hash drift during walk from {fen}"]
    while stack:
        move, undo = stack.pop()
        unmake(pos, move, undo)
    if pos.snapshot() != start:
        return [f"walk unmake failed to restore {fen}"]
    return []


def check_engine_expected(max_depth: int) -> list[str]:
    failures: list[str] = []
    for name, fen, expected in POSITIONS:
        pos = from_fen(fen)
        for depth, want in expected.items():
            if depth > max_depth:
                continue
            print(f"  engine {name} depth {depth} (want {want}) ...", flush=True)
            got = engine_perft(pos, depth)
            if got != want:
                failures.append(f"engine {name} depth {depth}: got {got} want {want}")
                if depth <= 2:
                    failures.append(_dump_divide(fen, depth))
    return failures


def check_engine_vs_oracle(fens: list[str], max_depth: int) -> list[str]:
    failures: list[str] = []
    for fen in fens:
        board = chess.Board(fen)
        pos = from_fen(fen)
        for depth in range(1, max_depth + 1):
            ref = oracle_perft(board, depth)
            got = engine_perft(pos, depth)
            if got != ref:
                failures.append(
                    f"vs-oracle {fen} depth {depth}: engine={got} oracle={ref}"
                )
                if depth <= 2:
                    failures.append(_dump_divide(fen, depth))
                break
    return failures


def random_fens(n: int = 20, seed: int = 20260903) -> list[str]:
    rng = random.Random(seed)
    out: list[str] = []
    attempts = 0
    while len(out) < n and attempts < n * 20:
        attempts += 1
        board = chess.Board()
        steps = rng.randint(6, 50)
        for _ in range(steps):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        if board.is_game_over():
            continue
        out.append(board.fen(en_passant="fen"))
    return out


def check(max_depth: int = 3) -> list[str]:
    """Brick 0 leftover: python-chess oracle only."""
    return check_oracle(max_depth=max_depth)


def check_brick_a(*, max_depth: int = 5, quick: bool = False) -> list[str]:
    suite_fens = [fen for _, fen, _ in POSITIONS]
    extras = random_fens(20)
    all_fens = suite_fens + extras
    failures: list[str] = []
    failures.extend(check_oracle(max_depth=3))
    failures.extend(check_fen_roundtrip(all_fens))
    failures.extend(check_legal_sets(all_fens))
    failures.extend(check_make_unmake(all_fens))
    failures.extend(check_fen_after_make(suite_fens, 2 if not quick else 1))
    failures.extend(check_fen_after_make(extras[:8], 1))
    failures.extend(check_unmake_walk(chess.STARTING_FEN, 80, 1))
    failures.extend(check_unmake_walk(POSITIONS[1][1], 60, 2))
    if failures:
        return failures
    depth = 3 if quick else max_depth
    failures.extend(check_engine_expected(depth))
    if failures:
        return failures
    rnd_depth = 2 if quick else 3
    failures.extend(check_engine_vs_oracle(extras, rnd_depth))
    if not quick:
        for fen in extras:
            board = chess.Board(fen)
            d3 = oracle_perft(board, 3)
            if d3 <= 25_000:
                failures.extend(check_engine_vs_oracle([fen], 4))
            if d3 <= 8_000:
                failures.extend(check_engine_vs_oracle([fen], 5))
    return failures


def main() -> None:
    import sys

    quick = "--quick" in sys.argv
    oracle_only = "--oracle" in sys.argv
    if oracle_only:
        failures = check(max_depth=3)
        label = "PERFT OK (python-chess oracle, depths <= 3)"
    else:
        failures = check_brick_a(max_depth=5, quick=quick)
        label = "PERFT OK (engine vs python-chess, Brick A)"
        if quick:
            label += " [--quick]"
    if failures:
        print("PERFT FAIL")
        for line in failures:
            print(f"  {line}")
        raise SystemExit(1)
    print(label)


if __name__ == "__main__":
    main()
