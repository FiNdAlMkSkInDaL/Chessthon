"""Independent, white-oriented positional feature reference for offline fitting.

These values are deliberately simple signed counts rather than engine answers.
They define units for fitting and must agree with a future native implementation
before any learned coefficient is allowed into Odin's mover.
"""

from __future__ import annotations

import chess


FEATURE_NAMES = (
    "pawn_isolated",
    "pawn_doubled",
    "pawn_supported",
    "passed_advance",
    "passed_blocked",
    "passer_friendly_king_distance",
    "passer_enemy_king_distance",
    "rook_open_file",
    "rook_semi_open_file",
    "king_shelter",
    "king_file_open",
)


def _pawn_files(board: chess.Board, color: chess.Color) -> list[int]:
    return [
        sum(1 for sq in board.pieces(chess.PAWN, color) if chess.square_file(sq) == file_)
        for file_ in range(8)
    ]


def _passed(board: chess.Board, color: chess.Color, square: chess.Square) -> bool:
    file_ = chess.square_file(square)
    rank = chess.square_rank(square)
    for enemy in board.pieces(chess.PAWN, not color):
        ef = chess.square_file(enemy)
        er = chess.square_rank(enemy)
        if abs(ef - file_) <= 1 and (er > rank if color else er < rank):
            return False
    return True


def _king_distance(left: chess.Square, right: chess.Square) -> int:
    return max(
        abs(chess.square_file(left) - chess.square_file(right)),
        abs(chess.square_rank(left) - chess.square_rank(right)),
    )


def _color_terms(board: chess.Board, color: chess.Color) -> list[int]:
    own_pawns = board.pieces(chess.PAWN, color)
    enemy_pawns = board.pieces(chess.PAWN, not color)
    files = _pawn_files(board, color)
    isolated = doubled = supported = passed_advance = passed_blocked = 0
    friendly_distance = enemy_distance = rook_open = rook_semi = 0
    for file_, count in enumerate(files):
        if count > 1:
            doubled += count - 1
        adjacent = (files[file_ - 1] if file_ else 0) + (files[file_ + 1] if file_ < 7 else 0)
        if count and not adjacent:
            isolated += count
    own_attacks = 0
    for pawn in own_pawns:
        own_attacks |= chess.BB_PAWN_ATTACKS[color][pawn]
    supported = sum(bool(own_attacks & chess.BB_SQUARES[pawn]) for pawn in own_pawns)
    own_king = board.king(color)
    enemy_king = board.king(not color)
    assert own_king is not None and enemy_king is not None
    for pawn in own_pawns:
        if not _passed(board, color, pawn):
            continue
        rank = chess.square_rank(pawn)
        advance = rank if color else 7 - rank
        passed_advance += advance
        push_rank = rank + 1 if color else rank - 1
        if not 0 <= push_rank < 8 or board.piece_at(chess.square(chess.square_file(pawn), push_rank)):
            passed_blocked += 1
        friendly_distance += _king_distance(own_king, pawn)
        enemy_distance += _king_distance(enemy_king, pawn)
    all_pawns = own_pawns | enemy_pawns
    for rook in board.pieces(chess.ROOK, color):
        file_ = chess.square_file(rook)
        own_file_pawns = files[file_]
        enemy_file_pawns = sum(1 for pawn in enemy_pawns if chess.square_file(pawn) == file_)
        if own_file_pawns == 0 and enemy_file_pawns == 0:
            rook_open += 1
        elif own_file_pawns == 0:
            rook_semi += 1

    king_file = chess.square_file(own_king)
    king_rank = chess.square_rank(own_king)
    direction = 1 if color else -1
    shelter = 0
    for file_ in range(max(0, king_file - 1), min(7, king_file + 1) + 1):
        for distance in (1, 2):
            rank = king_rank + direction * distance
            if 0 <= rank < 8 and chess.square(file_, rank) in own_pawns:
                shelter += 1
                break
    king_open = int(all(chess.square(king_file, rank) not in all_pawns for rank in range(8)))
    return [
        isolated, doubled, supported, passed_advance, passed_blocked,
        friendly_distance, enemy_distance, rook_open, rook_semi, shelter, king_open,
    ]


def extract(board: chess.Board) -> tuple[int, ...]:
    """Return white-minus-black feature units in ``FEATURE_NAMES`` order."""
    white = _color_terms(board, chess.WHITE)
    black = _color_terms(board, chess.BLACK)
    return tuple(left - right for left, right in zip(white, black))
