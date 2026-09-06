"""Brick B gates: legal search, clock, mate-in-1, draw policy, never-throw."""

from __future__ import annotations

import time

import chess

import agent
import history
from board_nb import from_fen
from eval_nb import pesto


def _legal(fen: str, time_left_ms: int) -> str:
    history.reset()
    move = agent.get_move(fen, time_left_ms)
    board = chess.Board(fen)
    legal = {m.uci() for m in board.legal_moves}
    if move not in legal:
        raise SystemExit(f"illegal {move!r} in {fen}")
    return move


def test_startpos_pesto_symmetric() -> None:
    pos = from_fen(chess.STARTING_FEN)
    if pesto(pos, tempo=False) != 0:
        raise SystemExit(f"startpos pesto without tempo is {pesto(pos, tempo=False)}, want 0")
    if pesto(pos, tempo=True) != 10:
        raise SystemExit(f"startpos pesto with tempo is {pesto(pos, tempo=True)}, want 10")


def test_mate_in_one() -> None:
    fen = "7k/5R2/6K1/8/8/8/8/8 w - - 0 1"
    move = _legal(fen, 3_000)
    if move != "f7f8":
        raise SystemExit(f"mate in 1: expected f7f8 got {move}")


def test_hanging_queen() -> None:
    fen = "4k3/8/8/8/8/8/7q/4K2R w K - 0 1"
    move = _legal(fen, 2_000)
    if move != "h1h2":
        raise SystemExit(f"hanging queen: expected h1h2 got {move}")


def test_underpromo_legal() -> None:
    fen = "8/5P1k/8/8/8/8/8/4K3 w - - 0 1"
    history.reset()
    move = agent.get_move(fen, 2_000)
    board = chess.Board(fen)
    if move not in {m.uci() for m in board.legal_moves}:
        raise SystemExit(f"underpromo position illegal {move}")
    if len(move) != 5:
        raise SystemExit(f"expected a promotion UCI, got {move}")


def test_panic_is_legal_and_fast() -> None:
    fen = chess.STARTING_FEN
    t0 = time.perf_counter()
    move = _legal(fen, 100)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if elapsed_ms > 200:
        raise SystemExit(f"panic search took {elapsed_ms:.0f} ms")
    if move not in {m.uci() for m in chess.Board(fen).legal_moves}:
        raise SystemExit(f"panic illegal {move}")


def test_clock_stays_inside_hard() -> None:
    fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
    budget = 800
    t0 = time.perf_counter()
    _legal(fen, budget)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    # hard = min(time-400, 2*soft); with 800 ms, hard is 400. One extra node is ok.
    if elapsed_ms > budget - 200:
        raise SystemExit(f"clock overran: {elapsed_ms:.0f} ms with {budget} ms left")


def test_fifty_winning_zeroes() -> None:
    # Extra pawn so a zeroing move exists. Winning + halfmove 90 → must pawn or capture.
    fen = "6k1/8/8/8/8/8/6P1/5QK1 w - - 90 1"
    history.reset()
    pos = from_fen(fen)
    from eval_nb import evaluate

    if not history.is_winning(evaluate(pos)):
        raise SystemExit("KQ+P vs K should be winning")
    board = chess.Board(fen)
    history.observe_served(board)
    filtered = history.filter_root_moves(board, list(board.legal_moves), True)
    if not filtered:
        raise SystemExit("filter emptied legal moves")
    if any(not board.is_zeroing(m) for m in filtered):
        raise SystemExit("winning fifty>=90 kept a quiet move")


def test_no_second_occurrence() -> None:
    fen = "6k1/8/8/8/8/8/6Q1/6K1 w - - 0 1"
    board = chess.Board(fen)
    history.reset()
    history.observe_served(board)
    qg2 = chess.Move.from_uci("g2g3")
    board.push(qg2)
    key = board._transposition_key()
    board.pop()
    history._seen[key] += 1
    filtered = history.filter_root_moves(board, list(board.legal_moves), True)
    uci = {m.uci() for m in filtered}
    if "g2g3" in uci:
        raise SystemExit("winning filter allowed a second occurrence")
    if not uci:
        raise SystemExit("winning filter removed every move")


def test_pawn_up_fifty_zeroes() -> None:
    fen = "4k3/8/8/8/8/8/4P3/4K3 w - - 90 1"
    history.reset()
    from eval_nb import evaluate

    pos = from_fen(fen)
    if not history.is_winning(evaluate(pos)):
        raise SystemExit(f"pawn-up should be winning, pesto={evaluate(pos)}")
    board = chess.Board(fen)
    history.observe_served(board)
    filtered = history.filter_root_moves(board, list(board.legal_moves), True)
    if any(not board.is_zeroing(m) for m in filtered):
        raise SystemExit("pawn-up fifty>=90 kept a quiet move")
    if not any(board.is_zeroing(m) for m in filtered):
        raise SystemExit("pawn-up fifty>=90 dropped every pawn move")


def test_losing_prefers_fifty_claim() -> None:
    # K vs Q, halfmove 98. Quiet → 99, opponent has a quiet → referee claims before they think.
    # Capture the queen and the game continues. When losing we must not take it.
    fen = "4k3/3Q4/8/8/8/8/8/4K3 b - - 98 1"
    history.reset()
    from eval_nb import evaluate

    pos = from_fen(fen)
    if not history.is_losing(evaluate(pos)):
        raise SystemExit(f"K vs Q should be losing for black, pesto={evaluate(pos)}")
    board = chess.Board(fen)
    history.observe_served(board)
    filtered = history.filter_root_moves(
        board, list(board.legal_moves), winning=False, losing=True
    )
    if any(board.is_zeroing(m) for m in filtered):
        raise SystemExit("losing filter kept a capture that avoids the fifty claim")
    if not filtered:
        raise SystemExit("losing fifty filter emptied legal moves")
    if not all(history._would_auto_claim_after(board, m) for m in filtered):
        raise SystemExit("losing fifty filter kept a move that does not auto-claim")


def test_losing_prefers_third_occurrence() -> None:
    fen = "4k3/8/8/8/8/8/8/4K2Q b - - 0 1"
    history.reset()
    from eval_nb import evaluate

    pos = from_fen(fen)
    if not history.is_losing(evaluate(pos)):
        raise SystemExit(f"K vs Q should be losing for black, pesto={evaluate(pos)}")
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
    if len(uci) != 1:
        raise SystemExit(f"losing filter should keep only claimers, got {sorted(uci)}")


def test_equal_does_not_seek_draws() -> None:
    fen = chess.STARTING_FEN
    history.reset()
    board = chess.Board(fen)
    history.observe_served(board)
    legal = list(board.legal_moves)
    filtered = history.filter_root_moves(board, legal, winning=False, losing=False)
    if {m.uci() for m in filtered} != {m.uci() for m in legal}:
        raise SystemExit("equal positions must not shrink the root list")


def test_never_throw_bad_fen() -> None:
    history.reset()
    move = agent.get_move("not a fen", 1_000)
    if not isinstance(move, str) or not move:
        raise SystemExit(f"bad fen returned {move!r}")


def test_game_ply_increments_by_two() -> None:
    history.reset()
    agent.get_move(chess.STARTING_FEN, 100)
    if history.game_ply() != 0:
        raise SystemExit(f"first ply want 0 got {history.game_ply()}")
    fen2 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    agent.get_move(fen2, 100)
    if history.game_ply() != 2:
        raise SystemExit(f"second call ply want 2 got {history.game_ply()}")


def main() -> None:
    test_startpos_pesto_symmetric()
    test_mate_in_one()
    test_hanging_queen()
    test_underpromo_legal()
    test_panic_is_legal_and_fast()
    test_clock_stays_inside_hard()
    test_fifty_winning_zeroes()
    test_no_second_occurrence()
    test_pawn_up_fifty_zeroes()
    test_losing_prefers_fifty_claim()
    test_losing_prefers_third_occurrence()
    test_equal_does_not_seek_draws()
    test_never_throw_bad_fen()
    test_game_ply_increments_by_two()
    print("BRICK B OK")


if __name__ == "__main__":
    main()
