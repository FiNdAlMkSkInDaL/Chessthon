"""Full-game python-chess transposition keys, absolute 600-ply counter, root draw policy.

Do not infer opponent UCI from FEN deltas. Process lives one game; tests call reset().
"""

from __future__ import annotations

from collections import Counter
import time

import chess

from board_nb import from_fen, make
from movegen_nb import generate_legal, move_uci

WIN_CP = 80
FIFTY_ZERO_FROM = 90
PLY_CAP = 600
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
    return False


def observe_served(board: chess.Board) -> None:
    global _game_ply, _started
    _started = True
    _game_ply = board.ply()
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


def _deadline_expired(deadline: float | None) -> bool:
    return deadline is not None and time.perf_counter() >= deadline


def _auto_claim_now(board: chess.Board, deadline: float | None = None) -> bool:
    """Model the referee's draw check for a hypothetical board state.

    ``_seen`` contains completed, real-game positions only.  A hypothetical
    state is a third occurrence when it already appears twice there; a legal
    child completes a claim when that child already appears twice.
    """
    # The referee resolves mate before any draw mechanism.
    if board.is_checkmate():
        return False
    if _seen[board._transposition_key()] >= 2:
        return True
    legal = list(board.legal_moves)
    if not legal or board.is_insufficient_material():
        return True
    if board.halfmove_clock >= 100:
        return True
    if board.halfmove_clock >= 99:
        for child in legal:
            if _deadline_expired(deadline):
                return False
            if board.is_zeroing(child):
                continue
            board.push(child)
            try:
                # A quiet mate/stalemate has no legal continuation and takes
                # precedence over a claim based on the intended move.
                if board.halfmove_clock >= 100 and any(board.legal_moves):
                    return True
            finally:
                board.pop()
    for child in legal:
        if _deadline_expired(deadline):
            return False
        board.push(child)
        try:
            if _seen[board._transposition_key()] >= 2:
                return True
        finally:
            board.pop()
    return False


def _opponent_can_force_auto_claim(
    board: chess.Board, move: chess.Move, deadline: float | None = None
) -> bool:
    """Whether ``move`` gives the opponent a reply that auto-draws next turn.

    The referee tests *our* legal replies before calling us.  One extra ply is
    therefore necessary: a root move can look harmless, yet the opponent can
    step into a position where any one of our legal moves completes threefold.
    """
    # Most winning roots have no twice-seen key at all, so a repetition claim
    # is impossible. A zeroing move from the high-fifty safety band also
    # cannot create a fifty-move claim in the next two plies.
    if _deadline_expired(deadline):
        return False
    if not any(count >= 2 for count in _seen.values()) and (
        board.halfmove_clock < FIFTY_ZERO_FROM or board.is_zeroing(move)
    ):
        return False
    board.push(move)
    try:
        if _auto_claim_now(board, deadline):
            return True
        replies = list(board.legal_moves)
        for reply in replies:
            if _deadline_expired(deadline):
                return False
            board.push(reply)
            try:
                if _auto_claim_now(board, deadline):
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
    *,
    deadline: float | None = None,
) -> list[chess.Move]:
    if not legal:
        return legal
    if not winning and board.halfmove_clock < FIFTY_ZERO_FROM:
        return legal
    kept: list[chess.Move] = []
    fifty = board.halfmove_clock
    for move in legal:
        board.push(move)
        key = board._transposition_key()
        checkmates = board.is_checkmate()
        draws_immediately = board.is_stalemate() or board.is_insufficient_material()
        board.pop()
        # Checkmate ends the game before any automatic draw claim.  In
        # particular, never discard a quiet mate merely because the
        # halfmove clock is in the zeroing-only safety band.
        if checkmates:
            kept.append(move)
            continue
        if winning and draws_immediately:
            continue
        if winning and fifty >= FIFTY_ZERO_FROM and not board.is_zeroing(move):
            continue
        if winning and _seen[key] >= 1:
            continue
        if winning and _opponent_can_force_auto_claim(board, move, deadline):
            continue
        kept.append(move)
    return kept if kept else legal
