"""Full-game python-chess transposition keys, 300-ply counter, root draw policy.

Do not infer opponent UCI from FEN deltas. Process lives one game; tests call reset().
"""

from __future__ import annotations

from collections import Counter

import chess

from board_nb import from_fen, make
from movegen_nb import generate_legal, move_uci

WIN_CP = 80
FIFTY_ZERO_FROM = 90
PLY_CAP = 300
ADJUDICATE_WINDOW = 16

_seen: Counter[object] = Counter()
_zkeys: list[int] = []
_game_ply = 0
_started = False


def reset() -> None:
    global _game_ply, _started
    _seen.clear()
    _zkeys.clear()
    _game_ply = 0
    _started = False


def game_ply() -> int:
    return _game_ply


def zkeys() -> list[int]:
    return _zkeys


def use_adjudication_eval() -> bool:
    return (PLY_CAP - _game_ply) <= ADJUDICATE_WINDOW


def observe_served(board: chess.Board) -> None:
    global _game_ply, _started
    if _started:
        _game_ply += 2
    else:
        _started = True
        _game_ply = 0
    _seen[board._transposition_key()] += 1
    _zkeys.append(from_fen(board.fen(en_passant="fen")).key)


def observe_our_uci(board: chess.Board, uci: str) -> None:
    pushed = board.copy(stack=False)
    pushed.push_uci(uci)
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


def is_winning(score_stm: int, *, adjudicate: bool = False) -> bool:
    if adjudicate:
        return score_stm > 0
    return score_stm >= WIN_CP


def is_losing(score_stm: int, *, adjudicate: bool = False) -> bool:
    if adjudicate:
        return score_stm < 0
    return score_stm <= -WIN_CP


def _auto_claim_now(board: chess.Board) -> bool:
    """Model the referee's draw check for a hypothetical board state."""
    if _seen[board._transposition_key()] >= 2:
        return True
    if board.halfmove_clock >= 100:
        return True
    legal = list(board.legal_moves)
    if board.halfmove_clock >= 99 and any(
        not board.is_zeroing(child) for child in legal
    ):
        return True
    for child in legal:
        board.push(child)
        try:
            if _seen[board._transposition_key()] >= 2:
                return True
        finally:
            board.pop()
    return False


def _would_auto_claim_after(board: chess.Board, move: chess.Move) -> bool:
    """True if the referee claims before the opponent's next callback."""
    board.push(move)
    try:
        return _auto_claim_now(board)
    finally:
        board.pop()


def _opponent_can_force_auto_claim(board: chess.Board, move: chess.Move) -> bool:
    """Whether ``move`` gives the opponent a reply that auto-draws next turn.

    The referee checks whether the side to move has any claim-completing legal
    move before calling it.  Looking only at the immediately returned board
    misses the common two-ply repetition cycle.
    """
    # Most winning roots have no twice-seen key at all, so a repetition claim
    # is impossible. A zeroing move from the high-fifty safety band also
    # cannot create a fifty-move claim in the next two plies.
    if not any(count >= 2 for count in _seen.values()) and (
        board.halfmove_clock < FIFTY_ZERO_FROM or board.is_zeroing(move)
    ):
        return False
    board.push(move)
    try:
        if _auto_claim_now(board):
            return True
        replies = list(board.legal_moves)
        for reply in replies:
            board.push(reply)
            try:
                if _auto_claim_now(board):
                    return True
            finally:
                board.pop()
        return False
    finally:
        board.pop()


def filter_root_moves(
    board: chess.Board,
    legal: list[chess.Move],
    winning: bool,
    losing: bool = False,
) -> list[chess.Move]:
    if not legal:
        return legal
    fifty = board.halfmove_clock
    if winning:
        kept: list[chess.Move] = []
        for move in legal:
            if fifty >= FIFTY_ZERO_FROM and not board.is_zeroing(move):
                continue
            board.push(move)
            key = board._transposition_key()
            board.pop()
            if _seen[key] >= 1:
                continue
            if _opponent_can_force_auto_claim(board, move):
                continue
            kept.append(move)
        return kept if kept else legal
    if not losing:
        return legal
    claimers = [move for move in legal if _would_auto_claim_after(board, move)]
    if claimers:
        return claimers
    setup: list[chess.Move] = []
    for move in legal:
        board.push(move)
        key = board._transposition_key()
        board.pop()
        if _seen[key] >= 1:
            setup.append(move)
        elif fifty >= 80 and not board.is_zeroing(move):
            setup.append(move)
    return setup if setup else legal
