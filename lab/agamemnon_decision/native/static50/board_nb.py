"""12 bitboards, mailbox, castle/ep/fifty, zobrist make/unmake. No search."""

from __future__ import annotations

from dataclasses import dataclass

from tables_nb import (
    BLACK,
    BP,
    BR,
    CASTLE_MASK,
    CHAR_TO_PIECE,
    EP_NONE,
    MASK64,
    N_PIECES,
    PIECE_CHAR,
    PROMO_UCI,
    WHITE,
    WP,
    WR,
    Z_CASTLE,
    Z_EP,
    Z_PIECE,
    Z_SIDE,
    parse_square,
    square_name,
)

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def pack_move(
    frm: int,
    to: int,
    promo: int = 0,
    *,
    capture: bool = False,
    ep: bool = False,
    castle: bool = False,
    double: bool = False,
) -> int:
    m = frm | (to << 6) | (promo << 12)
    if capture:
        m |= 1 << 15
    if ep:
        m |= 1 << 16
    if castle:
        m |= 1 << 17
    if double:
        m |= 1 << 18
    return m


def move_from(m: int) -> int:
    return m & 63


def move_to(m: int) -> int:
    return (m >> 6) & 63


def move_promo(m: int) -> int:
    return (m >> 12) & 7


def move_is_capture(m: int) -> bool:
    return bool(m & (1 << 15))


def move_is_ep(m: int) -> bool:
    return bool(m & (1 << 16))


def move_is_castle(m: int) -> bool:
    return bool(m & (1 << 17))


def move_is_double(m: int) -> bool:
    return bool(m & (1 << 18))


def move_uci(m: int) -> str:
    s = square_name(move_from(m)) + square_name(move_to(m))
    promo = move_promo(m)
    if promo:
        s += PROMO_UCI[promo]
    return s


@dataclass
class Undo:
    captured: int
    ep: int
    castle: int
    fifty: int
    fullmove: int
    side: int
    key: int


class Position:
    __slots__ = (
        "bb",
        "occ_w",
        "occ_b",
        "occ",
        "mb",
        "side",
        "castle",
        "ep",
        "fifty",
        "fullmove",
        "key",
    )

    def __init__(self) -> None:
        self.bb = [0] * N_PIECES
        self.occ_w = 0
        self.occ_b = 0
        self.occ = 0
        self.mb = [-1] * 64
        self.side = WHITE
        self.castle = 0
        self.ep = EP_NONE
        self.fifty = 0
        self.fullmove = 1
        self.key = 0

    def copy(self) -> Position:
        p = Position()
        p.bb = self.bb.copy()
        p.occ_w = self.occ_w
        p.occ_b = self.occ_b
        p.occ = self.occ
        p.mb = self.mb.copy()
        p.side = self.side
        p.castle = self.castle
        p.ep = self.ep
        p.fifty = self.fifty
        p.fullmove = self.fullmove
        p.key = self.key
        return p

    def snapshot(self) -> tuple:
        return (
            tuple(self.bb),
            self.occ_w,
            self.occ_b,
            self.occ,
            tuple(self.mb),
            self.side,
            self.castle,
            self.ep,
            self.fifty,
            self.fullmove,
            self.key,
        )


def _put(pos: Position, sq: int, piece: int, *, xor_hash: bool = True) -> None:
    bit = 1 << sq
    pos.bb[piece] |= bit
    if piece < 6:
        pos.occ_w |= bit
    else:
        pos.occ_b |= bit
    pos.occ |= bit
    pos.mb[sq] = piece
    if xor_hash:
        pos.key ^= Z_PIECE[piece][sq]


def _remove(pos: Position, sq: int, *, xor_hash: bool = True) -> int:
    piece = pos.mb[sq]
    bit = 1 << sq
    pos.bb[piece] &= MASK64 ^ bit
    if piece < 6:
        pos.occ_w &= MASK64 ^ bit
    else:
        pos.occ_b &= MASK64 ^ bit
    pos.occ &= MASK64 ^ bit
    pos.mb[sq] = -1
    if xor_hash:
        pos.key ^= Z_PIECE[piece][sq]
    return piece


def _square_attacked(pos: Position, sq: int, by_side: int) -> bool:
    """Attack test kept local so canonical EP hashing cannot import movegen.

    The FIDE repetition identity includes an en-passant field only when an
    en-passant capture is *legal*.  Calling ``generate_legal`` here would make
    ``make`` recurse while it is establishing the new EP key, so this small
    geometry-only attack routine is deliberately independent of movegen.
    """
    file = sq & 7
    rank = sq >> 3
    pawn = WP if by_side == WHITE else BP
    pawn_rank = rank - 1 if by_side == WHITE else rank + 1
    if 0 <= pawn_rank < 8:
        for pawn_file in (file - 1, file + 1):
            if 0 <= pawn_file < 8 and pos.mb[pawn_rank * 8 + pawn_file] == pawn:
                return True

    knight = 1 if by_side == WHITE else 7
    for df, dr in ((1, 2), (2, 1), (2, -1), (1, -2),
                   (-1, -2), (-2, -1), (-2, 1), (-1, 2)):
        nf, nr = file + df, rank + dr
        if 0 <= nf < 8 and 0 <= nr < 8 and pos.mb[nr * 8 + nf] == knight:
            return True

    king = 5 if by_side == WHITE else 11
    for df, dr in ((-1, -1), (-1, 0), (-1, 1), (0, -1),
                   (0, 1), (1, -1), (1, 0), (1, 1)):
        nf, nr = file + df, rank + dr
        if 0 <= nf < 8 and 0 <= nr < 8 and pos.mb[nr * 8 + nf] == king:
            return True

    bishop = 2 if by_side == WHITE else 8
    rook = WR if by_side == WHITE else BR
    queen = 4 if by_side == WHITE else 10
    for df, dr, sliders in (
        (1, 1, (bishop, queen)), (1, -1, (bishop, queen)),
        (-1, 1, (bishop, queen)), (-1, -1, (bishop, queen)),
        (1, 0, (rook, queen)), (-1, 0, (rook, queen)),
        (0, 1, (rook, queen)), (0, -1, (rook, queen)),
    ):
        nf, nr = file + df, rank + dr
        while 0 <= nf < 8 and 0 <= nr < 8:
            piece = pos.mb[nr * 8 + nf]
            if piece >= 0:
                if piece in sliders:
                    return True
                break
            nf += df
            nr += dr
    return False


def _legal_ep_from(pos: Position, frm: int) -> bool:
    """Whether the side-to-move can legally capture the raw EP square."""
    ep = pos.ep
    if ep == EP_NONE:
        return False
    side = pos.side
    pawn = WP if side == WHITE else BP
    cap_sq = ep - 8 if side == WHITE else ep + 8
    if pos.mb[frm] != pawn or not (0 <= cap_sq < 64):
        return False
    if pos.mb[cap_sq] != (BP if side == WHITE else WP):
        return False
    trial = pos.copy()
    _remove(trial, cap_sq, xor_hash=False)
    _remove(trial, frm, xor_hash=False)
    _put(trial, ep, pawn, xor_hash=False)
    king_bb = trial.bb[5 if side == WHITE else 11]
    if not king_bb:
        return False
    king_sq = (king_bb & -king_bb).bit_length() - 1
    return not _square_attacked(trial, king_sq, side ^ 1)


def ep_hashable(pos: Position) -> bool:
    """Return whether FIDE repetition identity retains ``pos.ep``.

    A syntactic FEN EP square is not enough: the capture must exist and must
    not expose our king.  This matches python-chess's transposition identity.
    """
    if pos.ep == EP_NONE:
        return False
    ep_file = pos.ep & 7
    ep_rank = pos.ep >> 3
    source_rank = ep_rank - 1 if pos.side == WHITE else ep_rank + 1
    if not 0 <= source_rank < 8:
        return False
    for source_file in (ep_file - 1, ep_file + 1):
        if 0 <= source_file < 8 and _legal_ep_from(pos, source_rank * 8 + source_file):
            return True
    return False


def compute_key(pos: Position) -> int:
    key = 0
    for piece in range(N_PIECES):
        bb = pos.bb[piece]
        while bb:
            bit = bb & -bb
            sq = bit.bit_length() - 1
            key ^= Z_PIECE[piece][sq]
            bb ^= bit
    key ^= Z_CASTLE[pos.castle]
    if ep_hashable(pos):
        key ^= Z_EP[pos.ep & 7]
    if pos.side == BLACK:
        key ^= Z_SIDE
    return key


def from_fen(fen: str) -> Position:
    parts = fen.split()
    if len(parts) < 4:
        raise ValueError(f"bad fen: {fen!r}")
    pos = Position()
    ranks = parts[0].split("/")
    if len(ranks) != 8:
        raise ValueError(f"bad fen ranks: {fen!r}")
    for ri, rank in enumerate(ranks):
        file = 0
        r = 7 - ri
        for ch in rank:
            if ch.isdigit():
                file += int(ch)
                continue
            if file >= 8 or ch not in CHAR_TO_PIECE:
                raise ValueError(f"bad fen: {fen!r}")
            _put(pos, r * 8 + file, CHAR_TO_PIECE[ch], xor_hash=False)
            file += 1
        if file != 8:
            raise ValueError(f"bad fen rank width: {fen!r}")
    pos.side = WHITE if parts[1] == "w" else BLACK
    pos.castle = 0
    if "K" in parts[2]:
        pos.castle |= 1
    if "Q" in parts[2]:
        pos.castle |= 2
    if "k" in parts[2]:
        pos.castle |= 4
    if "q" in parts[2]:
        pos.castle |= 8
    pos.ep = EP_NONE if parts[3] == "-" else parse_square(parts[3])
    pos.fifty = int(parts[4]) if len(parts) > 4 else 0
    pos.fullmove = int(parts[5]) if len(parts) > 5 else 1
    pos.key = compute_key(pos)
    return pos


def to_fen(pos: Position) -> str:
    rows: list[str] = []
    for rank in range(7, -1, -1):
        empty = 0
        row: list[str] = []
        for file in range(8):
            piece = pos.mb[rank * 8 + file]
            if piece < 0:
                empty += 1
                continue
            if empty:
                row.append(str(empty))
                empty = 0
            row.append(PIECE_CHAR[piece])
        if empty:
            row.append(str(empty))
        rows.append("".join(row))
    castle = ""
    if pos.castle & 1:
        castle += "K"
    if pos.castle & 2:
        castle += "Q"
    if pos.castle & 4:
        castle += "k"
    if pos.castle & 8:
        castle += "q"
    if not castle:
        castle = "-"
    ep = "-" if pos.ep == EP_NONE else square_name(pos.ep)
    stm = "w" if pos.side == WHITE else "b"
    return f"{'/'.join(rows)} {stm} {castle} {ep} {pos.fifty} {pos.fullmove}"


def make(pos: Position, move: int) -> Undo:
    frm = move_from(move)
    to = move_to(move)
    promo = move_promo(move)
    undo = Undo(
        captured=-1,
        ep=pos.ep,
        castle=pos.castle,
        fifty=pos.fifty,
        fullmove=pos.fullmove,
        side=pos.side,
        key=pos.key,
    )
    piece = pos.mb[frm]
    us = pos.side

    if pos.ep != EP_NONE and ep_hashable(pos):
        pos.key ^= Z_EP[pos.ep & 7]
        pos.ep = EP_NONE

    old_castle = pos.castle
    pos.castle &= CASTLE_MASK[frm] & CASTLE_MASK[to]
    if pos.castle != old_castle:
        pos.key ^= Z_CASTLE[old_castle] ^ Z_CASTLE[pos.castle]

    if move_is_ep(move):
        cap_sq = to - 8 if us == WHITE else to + 8
        undo.captured = _remove(pos, cap_sq)
        _remove(pos, frm)
        _put(pos, to, piece)
        pos.fifty = 0
    elif move_is_castle(move):
        _remove(pos, frm)
        _put(pos, to, piece)
        if to == 6:
            _remove(pos, 7)
            _put(pos, 5, WR)
        elif to == 2:
            _remove(pos, 0)
            _put(pos, 3, WR)
        elif to == 62:
            _remove(pos, 63)
            _put(pos, 61, BR)
        else:
            _remove(pos, 56)
            _put(pos, 59, BR)
        pos.fifty += 1
    else:
        if pos.mb[to] >= 0:
            undo.captured = _remove(pos, to)
        _remove(pos, frm)
        if promo:
            _put(pos, to, us * 6 + promo)
        else:
            _put(pos, to, piece)
        if piece == WP or piece == BP or undo.captured >= 0:
            pos.fifty = 0
        else:
            pos.fifty += 1
        if move_is_double(move):
            pos.ep = (frm + to) // 2

    pos.key ^= Z_SIDE
    pos.side ^= 1
    if us == BLACK:
        pos.fullmove += 1
    if pos.ep != EP_NONE and ep_hashable(pos):
        pos.key ^= Z_EP[pos.ep & 7]
    return undo


def unmake(pos: Position, move: int, undo: Undo) -> None:
    frm = move_from(move)
    to = move_to(move)
    promo = move_promo(move)
    us = undo.side

    if move_is_ep(move):
        mover = _remove(pos, to, xor_hash=False)
        _put(pos, frm, mover, xor_hash=False)
        cap_sq = to - 8 if us == WHITE else to + 8
        _put(pos, cap_sq, undo.captured, xor_hash=False)
    elif move_is_castle(move):
        mover = _remove(pos, to, xor_hash=False)
        _put(pos, frm, mover, xor_hash=False)
        if to == 6:
            _remove(pos, 5, xor_hash=False)
            _put(pos, 7, WR, xor_hash=False)
        elif to == 2:
            _remove(pos, 3, xor_hash=False)
            _put(pos, 0, WR, xor_hash=False)
        elif to == 62:
            _remove(pos, 61, xor_hash=False)
            _put(pos, 63, BR, xor_hash=False)
        else:
            _remove(pos, 59, xor_hash=False)
            _put(pos, 56, BR, xor_hash=False)
    else:
        mover = _remove(pos, to, xor_hash=False)
        if promo:
            _put(pos, frm, us * 6 + WP, xor_hash=False)
        else:
            _put(pos, frm, mover, xor_hash=False)
        if undo.captured >= 0:
            _put(pos, to, undo.captured, xor_hash=False)

    pos.ep = undo.ep
    pos.castle = undo.castle
    pos.fifty = undo.fifty
    pos.fullmove = undo.fullmove
    pos.side = undo.side
    pos.key = undo.key
