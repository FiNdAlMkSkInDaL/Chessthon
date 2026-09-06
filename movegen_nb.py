"""Ray-loop sliders + precomputed leapers. Legal movegen via make/unmake + in-check."""

from __future__ import annotations

from board_nb import (
    Position,
    make,
    move_is_capture,
    move_promo,
    move_uci,
    pack_move,
    unmake,
)
from tables_nb import (
    BISHOP_DIR_I,
    BK,
    BK_CASTLE,
    BLACK,
    BQ_CASTLE,
    BR,
    EP_NONE,
    KING_ATK,
    KNIGHT_ATK,
    MASK64,
    PAWN_ATK,
    PROMO_B,
    PROMO_N,
    PROMO_Q,
    PROMO_R,
    RAY_DIRS,
    ROOK_DIR_I,
    WHITE,
    WK,
    WK_CASTLE,
    WQ_CASTLE,
    WR,
    iter_bits,
    lsb,
    sq_rank,
)

PROMOS = (PROMO_N, PROMO_B, PROMO_R, PROMO_Q)


def sliding_attacks(sq: int, occ: int, dir_ids: tuple[int, ...]) -> int:
    attacks = 0
    f0 = sq & 7
    r0 = sq >> 3
    for d in dir_ids:
        df, dr = RAY_DIRS[d]
        f = f0 + df
        r = r0 + dr
        while 0 <= f < 8 and 0 <= r < 8:
            ns = r * 8 + f
            attacks |= 1 << ns
            if occ & (1 << ns):
                break
            f += df
            r += dr
    return attacks


def bishop_attacks(sq: int, occ: int) -> int:
    return sliding_attacks(sq, occ, BISHOP_DIR_I)


def rook_attacks(sq: int, occ: int) -> int:
    return sliding_attacks(sq, occ, ROOK_DIR_I)


def queen_attacks(sq: int, occ: int) -> int:
    return sliding_attacks(sq, occ, ROOK_DIR_I + BISHOP_DIR_I)


def square_attacked(pos: Position, sq: int, by_side: int) -> bool:
    occ = pos.occ
    if by_side == WHITE:
        if PAWN_ATK[BLACK][sq] & pos.bb[0]:
            return True
        if KNIGHT_ATK[sq] & pos.bb[1]:
            return True
        if KING_ATK[sq] & pos.bb[WK]:
            return True
        if bishop_attacks(sq, occ) & (pos.bb[2] | pos.bb[4]):
            return True
        if rook_attacks(sq, occ) & (pos.bb[3] | pos.bb[4]):
            return True
        return False
    if PAWN_ATK[WHITE][sq] & pos.bb[6]:
        return True
    if KNIGHT_ATK[sq] & pos.bb[7]:
        return True
    if KING_ATK[sq] & pos.bb[BK]:
        return True
    if bishop_attacks(sq, occ) & (pos.bb[8] | pos.bb[10]):
        return True
    if rook_attacks(sq, occ) & (pos.bb[9] | pos.bb[10]):
        return True
    return False


def in_check(pos: Position, side: int) -> bool:
    king = pos.bb[WK if side == WHITE else BK]
    if king == 0:
        return False
    return square_attacked(pos, lsb(king), side ^ 1)


def _emit_promos(out: list[int], frm: int, to: int, capture: bool) -> None:
    for promo in PROMOS:
        out.append(pack_move(frm, to, promo, capture=capture))


def generate_pseudo(pos: Position, out: list[int]) -> None:
    us = pos.side
    them = us ^ 1
    occ = pos.occ
    empty = MASK64 ^ occ
    ours = pos.occ_w if us == WHITE else pos.occ_b
    theirs = pos.occ_b if us == WHITE else pos.occ_w
    pawn = pos.bb[0 if us == WHITE else 6]
    push = 8 if us == WHITE else -8
    promo_rank = 7 if us == WHITE else 0
    start_rank = 1 if us == WHITE else 6
    ep = pos.ep

    for frm in iter_bits(pawn):
        to = frm + push
        if 0 <= to < 64 and (empty & (1 << to)):
            if sq_rank(to) == promo_rank:
                _emit_promos(out, frm, to, False)
            else:
                out.append(pack_move(frm, to))
                if sq_rank(frm) == start_rank:
                    to2 = frm + 2 * push
                    if empty & (1 << to2):
                        out.append(pack_move(frm, to2, double=True))
        for to in iter_bits(PAWN_ATK[us][frm] & theirs):
            if sq_rank(to) == promo_rank:
                _emit_promos(out, frm, to, True)
            else:
                out.append(pack_move(frm, to, capture=True))
        if ep != EP_NONE and (PAWN_ATK[us][frm] & (1 << ep)):
            out.append(pack_move(frm, ep, capture=True, ep=True))

    knight = pos.bb[1 if us == WHITE else 7]
    for frm in iter_bits(knight):
        for to in iter_bits(KNIGHT_ATK[frm] & ~ours):
            out.append(pack_move(frm, to, capture=bool(theirs & (1 << to))))

    bishop = pos.bb[2 if us == WHITE else 8]
    for frm in iter_bits(bishop):
        for to in iter_bits(bishop_attacks(frm, occ) & ~ours):
            out.append(pack_move(frm, to, capture=bool(theirs & (1 << to))))

    rook = pos.bb[3 if us == WHITE else 9]
    for frm in iter_bits(rook):
        for to in iter_bits(rook_attacks(frm, occ) & ~ours):
            out.append(pack_move(frm, to, capture=bool(theirs & (1 << to))))

    queen = pos.bb[4 if us == WHITE else 10]
    for frm in iter_bits(queen):
        for to in iter_bits(queen_attacks(frm, occ) & ~ours):
            out.append(pack_move(frm, to, capture=bool(theirs & (1 << to))))

    king_bb = pos.bb[WK if us == WHITE else BK]
    if king_bb:
        frm = lsb(king_bb)
        for to in iter_bits(KING_ATK[frm] & ~ours):
            out.append(pack_move(frm, to, capture=bool(theirs & (1 << to))))
        _generate_castles(pos, out, us, frm, occ)


def _generate_castles(pos: Position, out: list[int], us: int, ksq: int, occ: int) -> None:
    if us == WHITE:
        if ksq != 4:
            return
        if (pos.castle & WK_CASTLE) and pos.mb[7] == WR:
            if not (occ & ((1 << 5) | (1 << 6))):
                if not (
                    square_attacked(pos, 4, BLACK)
                    or square_attacked(pos, 5, BLACK)
                    or square_attacked(pos, 6, BLACK)
                ):
                    out.append(pack_move(4, 6, castle=True))
        if (pos.castle & WQ_CASTLE) and pos.mb[0] == WR:
            if not (occ & ((1 << 1) | (1 << 2) | (1 << 3))):
                if not (
                    square_attacked(pos, 4, BLACK)
                    or square_attacked(pos, 3, BLACK)
                    or square_attacked(pos, 2, BLACK)
                ):
                    out.append(pack_move(4, 2, castle=True))
        return
    if ksq != 60:
        return
    if (pos.castle & BK_CASTLE) and pos.mb[63] == BR:
        if not (occ & ((1 << 61) | (1 << 62))):
            if not (
                square_attacked(pos, 60, WHITE)
                or square_attacked(pos, 61, WHITE)
                or square_attacked(pos, 62, WHITE)
            ):
                out.append(pack_move(60, 62, castle=True))
    if (pos.castle & BQ_CASTLE) and pos.mb[56] == BR:
        if not (occ & ((1 << 57) | (1 << 58) | (1 << 59))):
            if not (
                square_attacked(pos, 60, WHITE)
                or square_attacked(pos, 59, WHITE)
                or square_attacked(pos, 58, WHITE)
            ):
                out.append(pack_move(60, 58, castle=True))


def generate_legal(pos: Position) -> list[int]:
    pseudo: list[int] = []
    generate_pseudo(pos, pseudo)
    legal: list[int] = []
    us = pos.side
    for move in pseudo:
        undo = make(pos, move)
        if not in_check(pos, us):
            legal.append(move)
        unmake(pos, move, undo)
    return legal


def generate_noisy(pos: Position) -> list[int]:
    """Legal captures and promotions. Qsearch uses this when not in check."""
    pseudo: list[int] = []
    generate_pseudo(pos, pseudo)
    legal: list[int] = []
    us = pos.side
    for move in pseudo:
        if not (move_is_capture(move) or move_promo(move)):
            continue
        undo = make(pos, move)
        if not in_check(pos, us):
            legal.append(move)
        unmake(pos, move, undo)
    return legal


def legal_uci(pos: Position) -> set[str]:
    return {move_uci(m) for m in generate_legal(pos)}


def perft(pos: Position, depth: int) -> int:
    try:
        import core_nb

        if core_nb.HAS_NUMBA:
            return core_nb.perft_pos(pos, depth)
    except Exception:
        pass
    if depth == 0:
        return 1
    moves = generate_legal(pos)
    if depth == 1:
        return len(moves)
    nodes = 0
    for move in moves:
        undo = make(pos, move)
        nodes += perft(pos, depth - 1)
        unmake(pos, move, undo)
    return nodes


def divide(pos: Position, depth: int) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for move in generate_legal(pos):
        undo = make(pos, move)
        nodes = perft(pos, depth - 1) if depth > 1 else 1
        unmake(pos, move, undo)
        rows.append((move_uci(move), nodes))
    rows.sort()
    return rows
