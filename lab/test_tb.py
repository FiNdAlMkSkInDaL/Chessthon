"""3-piece Syzygy root probe. Missing tables are a skip, not a fail."""

from __future__ import annotations

import chess

import tb_nb


def test_startpos_is_not_a_probe() -> None:
    board = chess.Board()
    if tb_nb.root_uci(board, list(board.legal_moves)) is not None:
        raise SystemExit("startpos must not hit 3-piece tables")


def test_castling_is_skipped() -> None:
    # 3 pieces but Syzygy refuses castling rights.
    fen = "4k3/8/8/8/8/8/8/R3K3 w Q - 0 1"
    board = chess.Board(fen)
    if chess.popcount(board.occupied) != 3:
        raise SystemExit("fixture should be 3 pieces")
    if tb_nb.root_uci(board, list(board.legal_moves)) is not None:
        raise SystemExit("castling-rights 3-piece must not probe")


def test_kqk_mates_when_tables_present() -> None:
    if tb_nb.load() <= 0:
        print("TB SKIP (no syzygy tables)")
        return
    fen = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"
    board = chess.Board(fen)
    uci = tb_nb.root_uci(board, list(board.legal_moves))
    if uci is None:
        raise SystemExit("KQk should probe when tables are present")
    board.push_uci(uci)
    if not board.is_checkmate():
        raise SystemExit(f"KQk root should be mate, got {uci}")


def test_kpk_promotes_when_tables_present() -> None:
    if tb_nb.load() <= 0:
        print("TB SKIP (no syzygy tables)")
        return
    fen = "8/5P1k/8/8/8/8/8/4K3 w - - 0 1"
    board = chess.Board(fen)
    uci = tb_nb.root_uci(board, list(board.legal_moves))
    if uci is None or len(uci) != 5:
        raise SystemExit(f"KPk root should promote, got {uci!r}")


def main() -> None:
    test_startpos_is_not_a_probe()
    test_castling_is_skipped()
    test_kqk_mates_when_tables_present()
    test_kpk_promotes_when_tables_present()
    print(f"TB OK (files={tb_nb.load()})")


if __name__ == "__main__":
    main()
