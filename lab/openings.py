"""Private mixed-FEN set. Rated games are unpublished; startpos-only tests lie.

Positions are 8–12 ply of reasonable play with |PeSTO| small. Not a book.
Regenerate: python -m lab.openings --regen
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import chess

from board_nb import from_fen
from eval_nb import pesto

DATA = Path(__file__).with_name("openings.fen")
SEED = 20260903
COUNT = 200
MIN_PLY = 8
MAX_PLY = 12
MAX_ABS_PESTO = 120
MIN_PIECES = 28

_CAPTURE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def _white_pesto(fen: str) -> int:
    pos = from_fen(fen)
    score = pesto(pos, tempo=False)
    return -score if pos.side else score


def _pick(board: chess.Board, rng: random.Random) -> chess.Move:
    moves = list(board.legal_moves)
    ranked: list[tuple[float, chess.Move]] = []
    for move in moves:
        score = rng.random()
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            if victim is not None:
                score += 8 + _CAPTURE[victim.piece_type]
        if board.gives_check(move):
            score += 4
        to_file = chess.square_file(move.to_square)
        to_rank = chess.square_rank(move.to_square)
        score += 1.5 - 0.25 * abs(to_file - 3.5) - 0.15 * abs(to_rank - 3.5)
        ranked.append((score, move))
    ranked.sort(key=lambda item: item[0], reverse=True)
    top = ranked[: min(4, len(ranked))]
    return rng.choice(top)[1]


def _fingerprint(board: chess.Board) -> str:
    return f"{board.board_fen()} {board.turn} {board.castling_rights} {board.ep_square}"


def generate(count: int = COUNT, seed: int = SEED) -> tuple[str, ...]:
    rng = random.Random(seed)
    found: list[str] = []
    seen: set[str] = set()
    attempts = 0
    while len(found) < count:
        attempts += 1
        if attempts > count * 400:
            raise RuntimeError(f"only generated {len(found)}/{count} openings")
        board = chess.Board()
        plies = rng.randint(MIN_PLY, MAX_PLY)
        ok = True
        for _ in range(plies):
            if board.is_game_over():
                ok = False
                break
            board.push(_pick(board, rng))
        if not ok or board.is_game_over():
            continue
        if len(board.piece_map()) < MIN_PIECES:
            continue
        key = _fingerprint(board)
        if key in seen:
            continue
        fen = board.fen()
        try:
            score = _white_pesto(fen)
        except ValueError:
            continue
        if abs(score) > MAX_ABS_PESTO:
            continue
        seen.add(key)
        found.append(fen)
    return tuple(found)


def load() -> tuple[str, ...]:
    if not DATA.is_file():
        raise FileNotFoundError(f"{DATA} missing; run python -m lab.openings --regen")
    fens = tuple(
        line.strip()
        for line in DATA.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )
    if len(fens) < COUNT:
        raise RuntimeError(f"{DATA} has {len(fens)} FENs; want {COUNT}")
    return fens[:COUNT]


def opening_fen(index: int, fens: tuple[str, ...] | None = None) -> str:
    pool = FENS if fens is None else fens
    return pool[index % len(pool)]


def write(fens: tuple[str, ...]) -> None:
    body = "\n".join(fens) + "\n"
    DATA.write_text(
        f"# {COUNT} private balanced FENs. Seed {SEED}. Not a contest book.\n{body}",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Private mixed-FEN openings for the gauntlet.")
    parser.add_argument("--regen", action="store_true", help="rewrite openings.fen")
    arguments = parser.parse_args()
    if arguments.regen:
        fens = generate()
        write(fens)
        print(f"wrote {len(fens)} FENs to {DATA}")
        return
    fens = load()
    print(f"{len(fens)} openings in {DATA}")
    print(fens[0])


FENS: tuple[str, ...]
try:
    FENS = load()
except FileNotFoundError:
    FENS = ()


if __name__ == "__main__":
    main()
