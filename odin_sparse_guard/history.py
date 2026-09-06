"""Reversible-window python-chess keys and current-referee state.

Do not infer opponent UCI from FEN deltas. Process lives one game; tests call reset().
"""

from __future__ import annotations

from collections import Counter
import time

import chess

from board_nb import from_fen, make
from movegen_nb import generate_legal, move_uci

PLY_CAP = 600

_seen: Counter[object] = Counter()
_zkeys: list[int] = []
_absolute_ply = 0
_started = False


def reset() -> None:
    global _absolute_ply, _started
    _seen.clear()
    _zkeys.clear()
    _absolute_ply = 0
    _started = False


def absolute_ply() -> int:
    """Absolute ply from FEN, equivalent to ``python-chess.Board.ply()``."""
    return _absolute_ply


def game_ply() -> int:
    """Compatibility name for callers; it is no longer request-relative."""
    return absolute_ply()


def zkeys() -> list[int]:
    return _zkeys


def reversible_root_keys(game_zkeys: list[int], fifty: int) -> list[int]:
    """Prior served/played keys still reachable since the last zeroing move."""
    prior = game_zkeys[:-1] if game_zkeys else []
    length = min(len(prior), max(0, int(fifty)))
    return list(prior[-length:]) if length else []


def use_adjudication_eval() -> bool:
    """Storm's material-adjudication mode no longer exists under the live rule."""
    return False


def observe_served(board: chess.Board) -> None:
    global _absolute_ply, _started
    _started = True
    _absolute_ply = board.ply()
    if board.halfmove_clock == 0:
        # FEN says the opponent made a pawn move/capture; no UCI inference is
        # required and no earlier board can occur again after this transition.
        _seen.clear()
        _zkeys.clear()
    _seen[board._transposition_key()] += 1
    _zkeys.append(from_fen(board.fen(en_passant="fen")).key)


def observe_our_uci(board: chess.Board, uci: str) -> None:
    pushed = board.copy(stack=False)
    pushed.push_uci(uci)
    if pushed.halfmove_clock == 0:
        _seen.clear()
        _zkeys.clear()
    _seen[pushed._transposition_key()] += 1
    pos = from_fen(board.fen(en_passant="fen"))
    packed = None
    for move in generate_legal(pos):
        if move_uci(move) == uci:
            packed = move
            break
    if packed is None:
        return
    make(pos, packed)
    _zkeys.append(pos.key)


def filter_root_moves(
    board: chess.Board,
    legal: list[chess.Move],
    winning: bool,
    *,
    deadline: float | None = None,
) -> list[chess.Move]:
    """All legal roots are searched.

    A static PeSTO score must not delete repetitions, quiet defences, or
    fifty-move resources.  The native search scores actual claims as draws
    using the complete recorded history, which lets a draw beat a loss and a
    searched win beat an optional draw.
    """
    del board, winning, deadline
    return legal
