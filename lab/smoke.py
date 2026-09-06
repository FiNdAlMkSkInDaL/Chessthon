"""Never-throw smoke for get_move. Not a strength test."""

from __future__ import annotations

import chess

import agent
import history

FENS = (
    chess.STARTING_FEN,
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    "4k3/8/8/8/8/8/8/4K3 w - - 0 1",
    "8/5P2/8/2k5/8/8/8/4K3 w - - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "not a fen",
)


def main() -> None:
    for fen in FENS:
        history.reset()
        move = agent.get_move(fen, 2_000)
        if not isinstance(move, str) or not move:
            raise SystemExit(f"empty or non-str move for {fen!r}: {move!r}")
        try:
            board = chess.Board(fen)
        except ValueError:
            continue
        legal = {m.uci() for m in board.legal_moves}
        if legal and move not in legal:
            raise SystemExit(f"illegal UCI {move!r} in {fen}")
        if move != "0000" and len(move) not in (4, 5):
            raise SystemExit(f"malformed UCI {move!r}")
    print("SMOKE OK")


if __name__ == "__main__":
    main()
