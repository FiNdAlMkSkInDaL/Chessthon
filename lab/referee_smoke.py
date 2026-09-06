"""Referee-shaped FEN fixtures. Tests history only — no agent import (avoids Numba JIT)."""

from __future__ import annotations

import chess

import history
from board_nb import from_fen
from eval_nb import evaluate, kingless_material, pesto

# ~8 curated positions mirroring referee edge cases (comments are documentation only).
REFEREE_FENS: tuple[tuple[str, str], ...] = (
    (
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "normal midgame — no draw filter, no adjudication eval",
    ),
    (
        "6k1/8/8/8/8/8/6P1/5QK1 w - - 90 1",
        "fifty-move high — winning side must play zeroing moves only",
    ),
    (
        "4k3/8/8/8/8/8/4P3/4K3 w - - 90 1",
        "fifty-move high pawn-up — winning filter keeps pawn pushes",
    ),
    (
        "6k1/8/8/8/8/8/6Q1/6K1 w - - 0 1",
        "repetition setup — second occurrence of a child key must be blocked when winning",
    ),
    (
        "4k3/3Q4/8/8/8/8/8/4K3 b - - 98 1",
        "losing fifty claim — quiet moves let referee auto-claim before opponent thinks",
    ),
    (
        "4k3/8/8/8/8/8/8/4K2Q b - - 0 1",
        "losing repetition — third occurrence of a king move should be preferred",
    ),
    (
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "equal middlegame — filter must not shrink legal moves",
    ),
    (
        "8/8/8/8/8/8/8/4K2k w - - 0 1",
        "bare kings near 300 plies — adjudication window switches to kingless material",
    ),
)


def test_adjudication_window_switches_eval() -> None:
    fen = REFEREE_FENS[7][0]
    pos = from_fen(fen)
    history.reset()
    history._game_ply = 283
    if history.use_adjudication_eval():
        raise SystemExit("adjudication eval should be off at ply 283")
    if evaluate(pos, adjudicate=False) != pesto(pos):
        raise SystemExit("pesto path mismatch below adjudication window")
    history._game_ply = 284
    if not history.use_adjudication_eval():
        raise SystemExit("adjudication eval should be on at ply 284")
    if evaluate(pos, adjudicate=True) != kingless_material(pos):
        raise SystemExit("kingless path mismatch inside adjudication window")


def test_winning_fifty_filter() -> None:
    for fen, _ in (REFEREE_FENS[1], REFEREE_FENS[2]):
        history.reset()
        pos = from_fen(fen)
        if not history.is_winning(evaluate(pos)):
            raise SystemExit(f"expected winning position: {fen}")
        board = chess.Board(fen)
        history.observe_served(board)
        filtered = history.filter_root_moves(board, list(board.legal_moves), True)
        if not filtered:
            raise SystemExit(f"winning filter emptied legal moves: {fen}")
        if any(not board.is_zeroing(m) for m in filtered):
            raise SystemExit(f"winning fifty>=90 kept a quiet move: {fen}")

    fen, _ = REFEREE_FENS[3]
    history.reset()
    board = chess.Board(fen)
    history.observe_served(board)
    repeat = chess.Move.from_uci("g2g3")
    board.push(repeat)
    key = board._transposition_key()
    board.pop()
    history._seen[key] += 1
    filtered = history.filter_root_moves(board, list(board.legal_moves), True)
    if chess.Move.from_uci("g2g3") in filtered:
        raise SystemExit("winning filter allowed a second occurrence")


def test_losing_claim_setup() -> None:
    fen, _ = REFEREE_FENS[4]
    history.reset()
    pos = from_fen(fen)
    if not history.is_losing(evaluate(pos)):
        raise SystemExit(f"expected losing position: {fen}")
    board = chess.Board(fen)
    history.observe_served(board)
    filtered = history.filter_root_moves(
        board, list(board.legal_moves), winning=False, losing=True
    )
    if any(board.is_zeroing(m) for m in filtered):
        raise SystemExit("losing filter kept a capture that avoids fifty claim")
    if not filtered:
        raise SystemExit("losing fifty filter emptied legal moves")
    if not all(history._would_auto_claim_after(board, m) for m in filtered):
        raise SystemExit("losing filter kept a move that does not auto-claim")

    fen, _ = REFEREE_FENS[5]
    history.reset()
    pos = from_fen(fen)
    if not history.is_losing(evaluate(pos)):
        raise SystemExit(f"expected losing position: {fen}")
    board = chess.Board(fen)
    history.observe_served(board)
    claim = chess.Move.from_uci("e8e7")
    board.push(claim)
    key = board._transposition_key()
    board.pop()
    history._seen[key] += 2
    filtered = history.filter_root_moves(
        board, list(board.legal_moves), winning=False, losing=True
    )
    uci = {m.uci() for m in filtered}
    if "e8e7" not in uci:
        raise SystemExit("losing filter dropped the third-occurrence move")


def main() -> None:
    test_adjudication_window_switches_eval()
    test_winning_fifty_filter()
    test_losing_claim_setup()
    print("REFEREE SMOKE OK")


if __name__ == "__main__":
    main()
