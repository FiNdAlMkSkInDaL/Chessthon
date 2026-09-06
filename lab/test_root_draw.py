"""Regression tests for referee claims that occur before our next callback."""

from __future__ import annotations

import chess

import history


def test_two_ply_repetition_trap_is_filtered_when_winning() -> None:
    """Round 10's Qd2/Qc1/Kf1/Kf2 cycle must not be re-entered when ahead."""
    # Position before our 62...Qc1+ in the actual round-10 game.
    board = chess.Board(
        "4r3/pRP1B2k/3P3p/4bp2/3p4/5Q2/3q4/5K2 b - - 28 62"
    )
    trap = chess.Move.from_uci("d2c1")
    reply = chess.Move.from_uci("f1f2")
    future = chess.Move.from_uci("c1d2")
    if trap not in board.legal_moves:
        raise SystemExit("round-10 trap root move is unexpectedly illegal")

    # If Black plays d2c1 and White answers f1f2, Black's c1d2 would make
    # the third D2 position. The referee claims before asking Black again.
    history.reset()
    board.push(trap)
    board.push(reply)
    board.push(future)
    history._seen[board._transposition_key()] = 2
    board.pop()
    board.pop()
    board.pop()
    original = board.fen()

    filtered = history.filter_root_moves(board, list(board.legal_moves), winning=True)
    if trap in filtered:
        raise SystemExit("winning filter kept the two-ply auto-claim trap")
    if board.fen() != original:
        raise SystemExit("draw filter did not restore the root board")


def test_quiet_mate_outranks_high_fifty_filter() -> None:
    """A non-zeroing mate must survive even when zeroing alternatives exist."""
    board = chess.Board("7k/8/5KQ1/8/8/8/P7/8 w - - 98 1")
    mate = chess.Move.from_uci("g6g7")
    if mate not in board.legal_moves:
        raise SystemExit("quiet mate regression position is invalid")
    board.push(mate)
    try:
        if not board.is_checkmate():
            raise SystemExit("Qg7 is no longer checkmate in regression position")
    finally:
        board.pop()
    if not any(board.is_zeroing(move) for move in board.legal_moves):
        raise SystemExit("quiet mate regression lacks a zeroing alternative")

    history.reset()
    filtered = history.filter_root_moves(board, list(board.legal_moves), winning=True)
    if mate not in filtered:
        raise SystemExit("high-fifty filter discarded a quiet checkmate")


def test_winner_avoids_immediate_insufficient_material() -> None:
    board = chess.Board("8/k7/2K1p3/3B4/8/8/8/8 w - - 0 1")
    drawing_capture = chess.Move.from_uci("d5e6")
    board.push(drawing_capture)
    try:
        if not board.is_insufficient_material():
            raise SystemExit("root insufficient-material fixture is invalid")
    finally:
        board.pop()

    history.reset()
    filtered = history.filter_root_moves(board, list(board.legal_moves), winning=True)
    if drawing_capture in filtered:
        raise SystemExit("winning root kept an immediate insufficient-material draw")
    if not filtered:
        raise SystemExit("winning root draw test removed every alternative")


def main() -> None:
    test_two_ply_repetition_trap_is_filtered_when_winning()
    test_quiet_mate_outranks_high_fifty_filter()
    test_winner_avoids_immediate_insufficient_material()
    print("ROOT DRAW POLICY OK")


if __name__ == "__main__":
    main()
