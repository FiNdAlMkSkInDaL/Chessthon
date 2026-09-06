"""Numba hot path: make/unmake, movegen, eval, perft, AB+qsearch.

Python Position stays the FEN/UCI facade. This module copies arrays and searches
in nopython. If import or warmup fails, search_nb keeps the Python path.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
NET = np.load(Path(__file__).with_name("value.npz"))["net"]
NN_LAST_BB = np.zeros(12, dtype=np.uint64)
NN_ACC = np.tile(NET[768].astype(np.int32), (2,1))
NN_ACC = np.concatenate([NN_ACC,np.zeros((65,32),np.int32)])
from numba import njit, objmode
from bitops_nb import lsb, msb

from eval_nb import EG_TABLE, MG_TABLE
from time_nb import MIN_ITER_MS
from tables_nb import (
    BISHOP_DIR_I,
    CASTLE_MASK,
    EP_NONE,
    KING_ATK,
    KNIGHT_ATK,
    PAWN_ATK,
    RAY_DIRS,
    ROOK_DIR_I,
    Z_CASTLE,
    Z_EP,
    Z_PIECE,
    Z_SIDE,
)

HAS_NUMBA = True
NUMBA_READY = False
WARMUP_S = 0.0
# Release tooling rejects a cold warmup at or above this target.  Runtime
# readiness itself means compilation succeeded: checking elapsed time only
# after LLVM has finished cannot save init time, and used to throw away an
# already-compiled hot path in an otherwise valid (< 90 s) process.
WARMUP_TARGET_S = 50.0

MAX_MOVES = 256
MAX_PLY = 96
MAX_DEPTH = 64
MATE = 32_000
INF = 32_001
DRAW = 0
ASPIRATION = 25
DELTA = 200
MATE_WIN = 31_000
RFP_MAX_D = 6
RFP_MARGIN = 80
NMP_MIN_D = 3
FF_MAX_D = 2
FF_MARGIN = 200
IIR_MIN_D = 4
SEE_PRUNE_MAX_D = 6
SEE_PRUNE_MARGIN = 80
HISTORY_MAX = 16_384
LMR_MIN_D = 3
LMR_TABLE = np.zeros((MAX_DEPTH + 1, MAX_MOVES + 1), dtype=np.int32)
for _depth in range(1, MAX_DEPTH + 1):
    for _move_number in range(1, MAX_MOVES + 1):
        LMR_TABLE[_depth, _move_number] = int(
            0.75 + np.log(_depth) * np.log(_move_number) / 2.25
        )
CHECK_EXT_PLY = 48
STALEMATE_SCAN_MAX_PIECES = 8
EXACT, LOWER, UPPER = 0, 1, 2
TT_BITS = 22
TT_SIZE = 1 << TT_BITS
TT_MASK = TT_SIZE - 1

OCC_W, OCC_B, OCC, SIDE, CASTLE, EP, FIFTY, FULL, KEY = range(9)
MG_ACC, EG_ACC, PHASE_ACC = 9, 10, 11
U_CAP, U_EP, U_CASTLE, U_FIFTY, U_FULL, U_SIDE, U_KEY = range(7)

KNIGHT_A = np.array(KNIGHT_ATK, dtype=np.uint64)
KING_A = np.array(KING_ATK, dtype=np.uint64)
PAWN_A = np.array(PAWN_ATK, dtype=np.uint64)
CASTLE_M = np.array(CASTLE_MASK, dtype=np.uint64)
Z_P = np.array(Z_PIECE, dtype=np.uint64)
Z_C = np.array(Z_CASTLE, dtype=np.uint64)
Z_E = np.array(Z_EP, dtype=np.uint64)
Z_S = np.uint64(Z_SIDE)
RAY_DF = np.array([d[0] for d in RAY_DIRS], dtype=np.int32)
RAY_DR = np.array([d[1] for d in RAY_DIRS], dtype=np.int32)
ROOK_DI = np.array(ROOK_DIR_I, dtype=np.int32)
BISHOP_DI = np.array(BISHOP_DIR_I, dtype=np.int32)
# Geometry only: rays computed from our existing direction definitions at import.
RAY_MASKS = np.zeros((64,8),dtype=np.uint64)
for _sq in range(64):
    for _di, (_df,_dr) in enumerate(RAY_DIRS):
        _f,_r=(_sq&7)+_df,(_sq>>3)+_dr
        _mask=0
        while 0<=_f<8 and 0<=_r<8:
            _mask |= 1<<(_r*8+_f)
            _f+=_df;_r+=_dr
        RAY_MASKS[_sq,_di]=np.uint64(_mask)
RAY_INCREASING=np.array([dr*8+df>0 for df,dr in RAY_DIRS],dtype=np.bool_)
MG_T = np.array(MG_TABLE, dtype=np.int32)
EG_T = np.array(EG_TABLE, dtype=np.int32)
PHASE_INC = np.array((0, 1, 1, 2, 4, 0), dtype=np.int32)
ADJ_V = np.array((100, 300, 300, 500, 900, 0), dtype=np.int32)
SEE_V = np.array((100, 300, 300, 500, 900, 20_000), dtype=np.int32)
PROMOS = np.array((4, 3, 2, 1), dtype=np.int32)

TT_KEY = np.zeros(TT_SIZE, dtype=np.uint64)
TT_MOVE = np.zeros(TT_SIZE, dtype=np.int32)
TT_SCORE = np.zeros(TT_SIZE, dtype=np.int16)
TT_DEPTH = np.zeros(TT_SIZE, dtype=np.uint8)
TT_GEN = np.zeros(TT_SIZE, dtype=np.uint8)
TT_AGE = np.zeros(1, dtype=np.int32)
TT_AGE[0] = 1

KILLERS = np.zeros((MAX_PLY, 2), dtype=np.int32)
HISTORY = np.zeros((12, 64), dtype=np.int32)
NODES = np.zeros(1, dtype=np.int64)
ABORTED = np.zeros(1, dtype=np.int32)


@njit(cache=False)
def popc(bb):
    v = np.uint64(bb)
    n = 0
    while v:
        v &= v - np.uint64(1)
        n += 1
    return n


@njit(cache=False)
def bit(sq):
    return np.uint64(1) << np.uint64(sq)


@njit(cache=False)
def pack_move(frm, to, promo, capture, ep, castle, double):
    m = np.int32(frm) | (np.int32(to) << 6) | (np.int32(promo) << 12)
    if capture:
        m |= np.int32(1) << 15
    if ep:
        m |= np.int32(1) << 16
    if castle:
        m |= np.int32(1) << 17
    if double:
        m |= np.int32(1) << 18
    return m


@njit(cache=False)
def m_from(m):
    return np.int32(m) & 63


@njit(cache=False)
def m_to(m):
    return (np.int32(m) >> 6) & 63


@njit(cache=False)
def m_promo(m):
    return (np.int32(m) >> 12) & 7


@njit(cache=False)
def m_cap(m):
    return (np.int32(m) & (np.int32(1) << 15)) != 0


@njit(cache=False)
def m_ep(m):
    return (np.int32(m) & (np.int32(1) << 16)) != 0


@njit(cache=False)
def m_castle(m):
    return (np.int32(m) & (np.int32(1) << 17)) != 0


@njit(cache=False)
def m_double(m):
    return (np.int32(m) & (np.int32(1) << 18)) != 0


@njit(cache=False)
def sliding(sq, occ, dirs):
    attacks = np.uint64(0)
    for i in range(dirs.shape[0]):
        d = dirs[i]
        ray = RAY_MASKS[sq,d]
        blockers = ray & np.uint64(occ)
        if blockers:
            nearest = lsb(blockers) if RAY_INCREASING[d] else msb(blockers)
            ray ^= RAY_MASKS[nearest,d]
        attacks |= ray
    return attacks


@njit(cache=False)
def bishop_att(sq, occ):
    return sliding(sq, occ, BISHOP_DI)


@njit(cache=False)
def rook_att(sq, occ):
    return sliding(sq, occ, ROOK_DI)


@njit(cache=False)
def queen_att(sq, occ):
    return bishop_att(sq, occ) | rook_att(sq, occ)


@njit(cache=False)
def sq_attacked(bb, sq, by_side, occ):
    sq = np.int32(sq)
    occ = np.uint64(occ)
    if by_side == 0:
        if PAWN_A[1, sq] & bb[0]:
            return True
        if KNIGHT_A[sq] & bb[1]:
            return True
        if KING_A[sq] & bb[5]:
            return True
        if bishop_att(sq, occ) & (bb[2] | bb[4]):
            return True
        if rook_att(sq, occ) & (bb[3] | bb[4]):
            return True
        return False
    if PAWN_A[0, sq] & bb[6]:
        return True
    if KNIGHT_A[sq] & bb[7]:
        return True
    if KING_A[sq] & bb[11]:
        return True
    if bishop_att(sq, occ) & (bb[8] | bb[10]):
        return True
    if rook_att(sq, occ) & (bb[9] | bb[10]):
        return True
    return False


@njit(cache=False)
def in_check_nb(bb, st, side):
    king = bb[5] if side == 0 else bb[11]
    if king == 0:
        return False
    return sq_attacked(bb, lsb(king), side ^ 1, st[OCC])


@njit(cache=False)
def ep_hashable_nb(bb, mb, st):
    """Whether the raw EP square belongs in the repetition/TT key.

    FEN retains a syntactic EP target after every double pawn push.  FIDE
    position identity retains it only when the side to move has a *legal* EP
    capture; a horizontally pinned pawn therefore does not make a distinct
    repetition position.  This helper is intentionally independent of
    ``gen_legal`` because ``make_nb`` is itself used to filter legal moves.
    """
    ep = np.int32(st[EP])
    if ep == EP_NONE:
        return False
    side = np.int32(st[SIDE])
    base = side * 6
    cap_sq = ep - 8 if side == 0 else ep + 8
    if cap_sq < 0 or cap_sq >= 64 or np.int32(mb[cap_sq]) != (6 if side == 0 else 0):
        return False
    candidates = PAWN_A[side ^ 1, ep] & bb[base]
    while candidates:
        frm = lsb(candidates)
        candidates &= candidates - np.uint64(1)
        trial = np.empty(12, dtype=np.uint64)
        for i in range(12):
            trial[i] = bb[i]
        trial[base] &= ~bit(frm)
        trial[base] |= bit(ep)
        trial[(side ^ 1) * 6] &= ~bit(cap_sq)
        occ = np.uint64(st[OCC])
        occ &= ~bit(frm)
        occ &= ~bit(cap_sq)
        occ |= bit(ep)
        king = trial[base + 5]
        if king and not sq_attacked(trial, lsb(king), side ^ 1, occ):
            return True
    return False


@njit(cache=False)
def put(bb, mb, st, sq, piece, xor_hash):
    b = bit(sq)
    bb[piece] |= b
    if piece < 6:
        st[OCC_W] |= b
    else:
        st[OCC_B] |= b
    st[OCC] |= b
    mb[sq] = np.int8(piece)
    sign = 1 if piece < 6 else -1
    st[MG_ACC] = np.uint64(np.int64(st[MG_ACC]) + sign * MG_T[piece, sq])
    st[EG_ACC] = np.uint64(np.int64(st[EG_ACC]) + sign * EG_T[piece, sq])
    st[PHASE_ACC] += np.uint64(PHASE_INC[piece % 6])
    if xor_hash:
        st[KEY] ^= Z_P[piece, sq]


@njit(cache=False)
def remove(bb, mb, st, sq, xor_hash):
    piece = np.int32(mb[sq])
    b = bit(sq)
    bb[piece] &= ~b
    if piece < 6:
        st[OCC_W] &= ~b
    else:
        st[OCC_B] &= ~b
    st[OCC] &= ~b
    mb[sq] = np.int8(-1)
    sign = 1 if piece < 6 else -1
    st[MG_ACC] = np.uint64(np.int64(st[MG_ACC]) - sign * MG_T[piece, sq])
    st[EG_ACC] = np.uint64(np.int64(st[EG_ACC]) - sign * EG_T[piece, sq])
    st[PHASE_ACC] -= np.uint64(PHASE_INC[piece % 6])
    if xor_hash:
        st[KEY] ^= Z_P[piece, sq]
    return piece


@njit(cache=False)
def make_nb(bb, mb, st, move, undo):
    frm = m_from(move)
    to = m_to(move)
    promo = m_promo(move)
    undo[U_CAP] = np.uint64(12)
    undo[U_EP] = st[EP]
    undo[U_CASTLE] = st[CASTLE]
    undo[U_FIFTY] = st[FIFTY]
    undo[U_FULL] = st[FULL]
    undo[U_SIDE] = st[SIDE]
    undo[U_KEY] = st[KEY]
    piece = np.int32(mb[frm])
    us = np.int32(st[SIDE])

    if np.int32(st[EP]) != EP_NONE and ep_hashable_nb(bb, mb, st):
        st[KEY] ^= Z_E[np.int32(st[EP]) & 7]
    if np.int32(st[EP]) != EP_NONE:
        st[EP] = np.uint64(EP_NONE)

    old_castle = np.int32(st[CASTLE])
    st[CASTLE] = np.uint64(old_castle) & CASTLE_M[frm] & CASTLE_M[to]
    if np.int32(st[CASTLE]) != old_castle:
        st[KEY] ^= Z_C[old_castle] ^ Z_C[np.int32(st[CASTLE])]

    if m_ep(move):
        cap_sq = to - 8 if us == 0 else to + 8
        undo[U_CAP] = np.uint64(remove(bb, mb, st, cap_sq, True))
        remove(bb, mb, st, frm, True)
        put(bb, mb, st, to, piece, True)
        st[FIFTY] = np.uint64(0)
    elif m_castle(move):
        remove(bb, mb, st, frm, True)
        put(bb, mb, st, to, piece, True)
        if to == 6:
            remove(bb, mb, st, 7, True)
            put(bb, mb, st, 5, 3, True)
        elif to == 2:
            remove(bb, mb, st, 0, True)
            put(bb, mb, st, 3, 3, True)
        elif to == 62:
            remove(bb, mb, st, 63, True)
            put(bb, mb, st, 61, 9, True)
        else:
            remove(bb, mb, st, 56, True)
            put(bb, mb, st, 59, 9, True)
        st[FIFTY] += np.uint64(1)
    else:
        if mb[to] >= 0:
            undo[U_CAP] = np.uint64(remove(bb, mb, st, to, True))
        remove(bb, mb, st, frm, True)
        if promo:
            put(bb, mb, st, to, us * 6 + promo, True)
        else:
            put(bb, mb, st, to, piece, True)
        if piece == 0 or piece == 6 or np.int32(undo[U_CAP]) < 12:
            st[FIFTY] = np.uint64(0)
        else:
            st[FIFTY] += np.uint64(1)
        if m_double(move):
            st[EP] = np.uint64((frm + to) // 2)

    st[KEY] ^= Z_S
    st[SIDE] ^= np.uint64(1)
    if us == 1:
        st[FULL] += np.uint64(1)
    if np.int32(st[EP]) != EP_NONE and ep_hashable_nb(bb, mb, st):
        st[KEY] ^= Z_E[np.int32(st[EP]) & 7]


@njit(cache=False)
def unmake_nb(bb, mb, st, move, undo):
    frm = m_from(move)
    to = m_to(move)
    promo = m_promo(move)
    us = np.int32(undo[U_SIDE])
    cap = np.int32(undo[U_CAP])

    if m_ep(move):
        mover = remove(bb, mb, st, to, False)
        put(bb, mb, st, frm, mover, False)
        cap_sq = to - 8 if us == 0 else to + 8
        put(bb, mb, st, cap_sq, cap, False)
    elif m_castle(move):
        mover = remove(bb, mb, st, to, False)
        put(bb, mb, st, frm, mover, False)
        if to == 6:
            remove(bb, mb, st, 5, False)
            put(bb, mb, st, 7, 3, False)
        elif to == 2:
            remove(bb, mb, st, 3, False)
            put(bb, mb, st, 0, 3, False)
        elif to == 62:
            remove(bb, mb, st, 61, False)
            put(bb, mb, st, 63, 9, False)
        else:
            remove(bb, mb, st, 59, False)
            put(bb, mb, st, 56, 9, False)
    else:
        mover = remove(bb, mb, st, to, False)
        if promo:
            put(bb, mb, st, frm, us * 6 + 0, False)
        else:
            put(bb, mb, st, frm, mover, False)
        if cap < 12:
            put(bb, mb, st, to, cap, False)

    st[EP] = undo[U_EP]
    st[CASTLE] = undo[U_CASTLE]
    st[FIFTY] = undo[U_FIFTY]
    st[FULL] = undo[U_FULL]
    st[SIDE] = undo[U_SIDE]
    st[KEY] = undo[U_KEY]


@njit(cache=False)
def emit_promos(out, n, frm, to, capture):
    for i in range(4):
        out[n] = pack_move(frm, to, PROMOS[i], capture, False, False, False)
        n += 1
    return n


@njit(cache=False)
def gen_castles(bb, mb, st, out, n, us, ksq, occ):
    if us == 0:
        if ksq != 4:
            return n
        if (np.int32(st[CASTLE]) & 1) and mb[7] == 3:
            if not (occ & (bit(5) | bit(6))):
                if not (
                    sq_attacked(bb, 4, 1, occ)
                    or sq_attacked(bb, 5, 1, occ)
                    or sq_attacked(bb, 6, 1, occ)
                ):
                    out[n] = pack_move(4, 6, 0, False, False, True, False)
                    n += 1
        if (np.int32(st[CASTLE]) & 2) and mb[0] == 3:
            if not (occ & (bit(1) | bit(2) | bit(3))):
                if not (
                    sq_attacked(bb, 4, 1, occ)
                    or sq_attacked(bb, 3, 1, occ)
                    or sq_attacked(bb, 2, 1, occ)
                ):
                    out[n] = pack_move(4, 2, 0, False, False, True, False)
                    n += 1
        return n
    if ksq != 60:
        return n
    if (np.int32(st[CASTLE]) & 4) and mb[63] == 9:
        if not (occ & (bit(61) | bit(62))):
            if not (
                sq_attacked(bb, 60, 0, occ)
                or sq_attacked(bb, 61, 0, occ)
                or sq_attacked(bb, 62, 0, occ)
            ):
                out[n] = pack_move(60, 62, 0, False, False, True, False)
                n += 1
    if (np.int32(st[CASTLE]) & 8) and mb[56] == 9:
        if not (occ & (bit(57) | bit(58) | bit(59))):
            if not (
                sq_attacked(bb, 60, 0, occ)
                or sq_attacked(bb, 59, 0, occ)
                or sq_attacked(bb, 58, 0, occ)
            ):
                out[n] = pack_move(60, 58, 0, False, False, True, False)
                n += 1
    return n


@njit(cache=False)
def gen_pseudo(bb, mb, st, out):
    us = np.int32(st[SIDE])
    occ = np.uint64(st[OCC])
    empty = ~occ
    ours = np.uint64(st[OCC_W] if us == 0 else st[OCC_B])
    theirs = np.uint64(st[OCC_B] if us == 0 else st[OCC_W])
    pawn = bb[0 if us == 0 else 6]
    push = 8 if us == 0 else -8
    promo_rank = 7 if us == 0 else 0
    start_rank = 1 if us == 0 else 6
    ep = np.int32(st[EP])
    n = 0

    bb_p = pawn
    while bb_p:
        frm = lsb(bb_p)
        bb_p &= bb_p - np.uint64(1)
        to = frm + push
        if 0 <= to < 64 and (empty & bit(to)):
            if (to >> 3) == promo_rank:
                n = emit_promos(out, n, frm, to, False)
            else:
                out[n] = pack_move(frm, to, 0, False, False, False, False)
                n += 1
                if (frm >> 3) == start_rank:
                    to2 = frm + 2 * push
                    if empty & bit(to2):
                        out[n] = pack_move(frm, to2, 0, False, False, False, True)
                        n += 1
        atk = PAWN_A[us, frm] & theirs
        while atk:
            to = lsb(atk)
            atk &= atk - np.uint64(1)
            if (to >> 3) == promo_rank:
                n = emit_promos(out, n, frm, to, True)
            else:
                out[n] = pack_move(frm, to, 0, True, False, False, False)
                n += 1
        if ep != EP_NONE and (PAWN_A[us, frm] & bit(ep)):
            out[n] = pack_move(frm, ep, 0, True, True, False, False)
            n += 1

    kn = bb[1 if us == 0 else 7]
    while kn:
        frm = lsb(kn)
        kn &= kn - np.uint64(1)
        dest = KNIGHT_A[frm] & ~ours
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1

    bi = bb[2 if us == 0 else 8]
    while bi:
        frm = lsb(bi)
        bi &= bi - np.uint64(1)
        dest = bishop_att(frm, occ) & ~ours
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1

    rk = bb[3 if us == 0 else 9]
    while rk:
        frm = lsb(rk)
        rk &= rk - np.uint64(1)
        dest = rook_att(frm, occ) & ~ours
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1

    qn = bb[4 if us == 0 else 10]
    while qn:
        frm = lsb(qn)
        qn &= qn - np.uint64(1)
        dest = queen_att(frm, occ) & ~ours
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1

    king_bb = bb[5 if us == 0 else 11]
    if king_bb:
        frm = lsb(king_bb)
        dest = KING_A[frm] & ~ours
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1
        n = gen_castles(bb, mb, st, out, n, us, frm, occ)
    return n


@njit(cache=False)
def gen_pseudo_noisy(bb, mb, st, out):
    us = np.int32(st[SIDE])
    occ = np.uint64(st[OCC])
    empty = ~occ
    ours = np.uint64(st[OCC_W] if us == 0 else st[OCC_B])
    theirs = np.uint64(st[OCC_B] if us == 0 else st[OCC_W])
    pawn = bb[0 if us == 0 else 6]
    push = 8 if us == 0 else -8
    promo_rank = 7 if us == 0 else 0
    start_rank = 1 if us == 0 else 6
    ep = np.int32(st[EP])
    n = 0

    bb_p = pawn
    while bb_p:
        frm = lsb(bb_p)
        bb_p &= bb_p - np.uint64(1)
        to = frm + push
        if 0 <= to < 64 and (empty & bit(to)):
            if (to >> 3) == promo_rank:
                n = emit_promos(out, n, frm, to, False)
        atk = PAWN_A[us, frm] & theirs
        while atk:
            to = lsb(atk)
            atk &= atk - np.uint64(1)
            if (to >> 3) == promo_rank:
                n = emit_promos(out, n, frm, to, True)
            else:
                out[n] = pack_move(frm, to, 0, True, False, False, False)
                n += 1
        if ep != EP_NONE and (PAWN_A[us, frm] & bit(ep)):
            out[n] = pack_move(frm, ep, 0, True, True, False, False)
            n += 1

    kn = bb[1 if us == 0 else 7]
    while kn:
        frm = lsb(kn)
        kn &= kn - np.uint64(1)
        dest = KNIGHT_A[frm] & theirs
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1

    bi = bb[2 if us == 0 else 8]
    while bi:
        frm = lsb(bi)
        bi &= bi - np.uint64(1)
        dest = bishop_att(frm, occ) & theirs
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1

    rk = bb[3 if us == 0 else 9]
    while rk:
        frm = lsb(rk)
        rk &= rk - np.uint64(1)
        dest = rook_att(frm, occ) & theirs
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1

    qn = bb[4 if us == 0 else 10]
    while qn:
        frm = lsb(qn)
        qn &= qn - np.uint64(1)
        dest = queen_att(frm, occ) & theirs
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1

    king_bb = bb[5 if us == 0 else 11]
    if king_bb:
        frm = lsb(king_bb)
        dest = KING_A[frm] & theirs
        while dest:
            to = lsb(dest)
            dest &= dest - np.uint64(1)
            cap = (theirs & bit(to)) != 0
            out[n] = pack_move(frm, to, 0, cap, False, False, False)
            n += 1
    return n


@njit(cache=False)
def pinned_pieces_nb(bb, mb, st, king, us):
    pinned = np.uint64(0)
    ours = st[OCC_W] if us == 0 else st[OCC_B]
    base = (us^1)*6
    for d in range(8):
        blockers = RAY_MASKS[king,d] & st[OCC]
        if not blockers:
            continue
        first = lsb(blockers) if RAY_INCREASING[d] else msb(blockers)
        if not (bit(first) & ours):
            continue
        beyond = RAY_MASKS[first,d] & st[OCC]
        if not beyond:
            continue
        second = lsb(beyond) if RAY_INCREASING[d] else msb(beyond)
        sliders = (bb[base+3] | bb[base+4]) if d < 4 else (bb[base+2] | bb[base+4])
        if sliders & bit(second):
            pinned |= bit(first)
    return pinned


@njit(cache=False)
def move_safe_nb(bb, mb, st, move, king, checked, pinned):
    """Test attacks in the resulting occupancy without mutating game state.

    Pseudo-generator already checks castling origin/transit squares. Captured
    attackers must be removed from attack masks (especially EP checking pawns).
    EP bypasses the pin shortcut because two occupied squares disappear.
    """
    frm = m_from(move)
    to = m_to(move)
    us = np.int32(st[SIDE])
    mover = np.int32(mb[frm])
    is_king = mover%6 == 5
    ep = m_ep(move)
    if not checked and not is_king and not ep and not (pinned & bit(frm)):
        return True
    occ = (np.uint64(st[OCC]) & ~bit(frm)) | bit(to)
    captured = bit(to)
    if ep:
        captured = bit(to-8 if us == 0 else to+8)
        occ &= ~captured
    if m_castle(move):
        if to == 6:
            occ = (occ & ~bit(7)) | bit(5)
        elif to == 2:
            occ = (occ & ~bit(0)) | bit(3)
        elif to == 62:
            occ = (occ & ~bit(63)) | bit(61)
        else:
            occ = (occ & ~bit(56)) | bit(59)
    sq = to if is_king else king
    base = (us^1)*6
    surviving = ~captured
    if PAWN_A[us,sq] & bb[base] & surviving:
        return False
    if KNIGHT_A[sq] & bb[base+1] & surviving:
        return False
    if KING_A[sq] & bb[base+5] & surviving:
        return False
    if bishop_att(sq,occ) & (bb[base+2] | bb[base+4]) & surviving:
        return False
    if rook_att(sq,occ) & (bb[base+3] | bb[base+4]) & surviving:
        return False
    return True


@njit(cache=False)
def gen_legal(bb, mb, st, out, scratch):
    nps = gen_pseudo(bb, mb, st, scratch)
    us = np.int32(st[SIDE])
    king = lsb(bb[us*6+5])
    checked = in_check_nb(bb, st, us)
    pinned = pinned_pieces_nb(bb, mb, st, king, us) if not checked else np.uint64(0)
    n = 0
    for i in range(nps):
        mv = scratch[i]
        if move_safe_nb(bb, mb, st, mv, king, checked, pinned):
            out[n] = mv
            n += 1
    return n


@njit(cache=False)
def has_legal_nb(bb, mb, st, scratch, undo):
    """Return after the first legal move without materialising a move list."""
    nps = gen_pseudo(bb, mb, st, scratch)
    us = np.int32(st[SIDE])
    king = lsb(bb[us*6+5])
    checked = in_check_nb(bb, st, us)
    pinned = pinned_pieces_nb(bb, mb, st, king, us) if not checked else np.uint64(0)
    for i in range(nps):
        mv = scratch[i]
        if move_safe_nb(bb, mb, st, mv, king, checked, pinned):
            return True
    return False


@njit(cache=False)
def gives_check_nb(bb, mb, st, move, undo):
    """Our attack masks after a legal move; no hash/evaluation make/unmake."""
    us = np.int32(st[SIDE])
    base = us*6
    enemy_king = bb[(us^1)*6+5]
    if enemy_king == 0:
        return False
    king = lsb(enemy_king)
    frm = m_from(move)
    to = m_to(move)
    from_bit = bit(frm)
    to_bit = bit(to)
    occ = (st[OCC] & ~from_bit) | to_bit
    pawns = bb[base] & ~from_bit
    knights = bb[base+1] & ~from_bit
    bishops = bb[base+2] & ~from_bit
    rooks = bb[base+3] & ~from_bit
    queens = bb[base+4] & ~from_bit
    kings = bb[base+5] & ~from_bit
    pt = m_promo(move) if m_promo(move) else np.int32(mb[frm])%6
    if pt == 0: pawns |= to_bit
    elif pt == 1: knights |= to_bit
    elif pt == 2: bishops |= to_bit
    elif pt == 3: rooks |= to_bit
    elif pt == 4: queens |= to_bit
    else: kings |= to_bit
    if m_ep(move):
        occ &= ~bit(to-8 if us == 0 else to+8)
    if m_castle(move):
        rf = 7 if to == 6 else 0 if to == 2 else 63 if to == 62 else 56
        rt = 5 if to == 6 else 3 if to == 2 else 61 if to == 62 else 59
        rooks = (rooks & ~bit(rf)) | bit(rt)
        occ = (occ & ~bit(rf)) | bit(rt)
    if PAWN_A[us^1,king] & pawns: return True
    if KNIGHT_A[king] & knights: return True
    if KING_A[king] & kings: return True
    if bishop_att(king,occ) & (bishops | queens): return True
    if rook_att(king,occ) & (rooks | queens): return True
    return False


@njit(cache=False)
def fifty_claim_nb(bb, mb, st, legal_moves, nlegal, scratch, undo):
    """Actual fifty moves; callers establish mate/stalemate precedence first."""
    return nlegal > 0 and np.int32(st[FIFTY]) >= 100


@njit(cache=False)
def gen_noisy(bb, mb, st, out, scratch):
    nps = gen_pseudo_noisy(bb, mb, st, scratch)
    us = np.int32(st[SIDE])
    king = lsb(bb[us*6+5])
    checked = in_check_nb(bb, st, us)
    pinned = pinned_pieces_nb(bb, mb, st, king, us) if not checked else np.uint64(0)
    n = 0
    for i in range(nps):
        mv = scratch[i]
        if not (m_cap(mv) or m_promo(mv)):
            continue
        if move_safe_nb(bb, mb, st, mv, king, checked, pinned):
            out[n] = mv
            n += 1
    return n


@njit(cache=False)
def pesto_reference_nb(bb, st, tempo):
    mg_w = 0
    mg_b = 0
    eg_w = 0
    eg_b = 0
    phase = 0
    for piece in range(6):
        inc = PHASE_INC[piece]
        b = bb[piece]
        while b:
            sq = lsb(b)
            b &= b - np.uint64(1)
            mg_w += MG_T[piece, sq]
            eg_w += EG_T[piece, sq]
            phase += inc
        bp = piece + 6
        b = bb[bp]
        while b:
            sq = lsb(b)
            b &= b - np.uint64(1)
            mg_b += MG_T[bp, sq]
            eg_b += EG_T[bp, sq]
            phase += inc
    if phase > 24:
        phase = 24
    score = (mg_w - mg_b) * phase + (eg_w - eg_b) * (24 - phase)
    score //= 24
    if np.int32(st[SIDE]) == 1:
        score = -score
    if tempo:
        # Normalise perspective first so either mover receives the bonus.
        score += 10
    return np.int32(score)


@njit(cache=False)
def pesto_nb(bb, st, tempo):
    """Exact PeSTO from reversible accumulators, including promotions."""
    phase = min(24, np.int64(st[PHASE_ACC]))
    score = (np.int64(st[MG_ACC]) * phase + np.int64(st[EG_ACC]) * (24 - phase)) // 24
    if np.int32(st[SIDE]) == 1:
        score = -score
    if tempo:
        score += 10
    return np.int32(score)


@njit(cache=False)
def insufficient_material_nb(bb):
    """Numba mirror of python-chess's conservative dead-material cases."""
    heavy = bb[0] | bb[3] | bb[4] | bb[6] | bb[9] | bb[10]
    if heavy:
        return False
    knights = bb[1] | bb[7]
    bishops = bb[2] | bb[8]
    if knights:
        return (not bishops) and popc(knights) == 1
    if bishops:
        dark = np.uint64(0xAA55AA55AA55AA55)
        light = np.uint64(0x55AA55AA55AA55AA)
        return not (bishops & dark) or not (bishops & light)
    return True


@njit(cache=False)
def kingless_nb(bb, st):
    w = 0
    b = 0
    for pt in range(5):
        w += popc(bb[pt]) * ADJ_V[pt]
        b += popc(bb[pt + 6]) * ADJ_V[pt]
    score = w - b
    if np.int32(st[SIDE]) == 1:
        score = -score
    return np.int32(score)


# Original Odin positional features; weights fitted offline on private labels.
FEATURE_MG = np.array([-6, -14, 0, 6, -17, -4, 0, 6, 1, 0, -59, 0, 0, 4, 1, 2, 2, 0, 0, -19, -15, -40, -9, 50], dtype=np.int32)
FEATURE_EG = np.array([-12, -6, 8, 8, -38, -5, 5, 13, 11, 0, -7, 72, 3, 5, 4, 5, 2, 3, 10, 12, 40, 24, 50, 50], dtype=np.int32)
FEATURE_FILES = np.array([0x0101010101010101 << f for f in range(8)], dtype=np.uint64)
FEATURE_PASSED = np.zeros((2,64), dtype=np.uint64)
for _c in range(2):
    for _s in range(64):
        _mask = 0
        for _f in range(max(0,(_s&7)-1), min(7,(_s&7)+1)+1):
            for _r in (range((_s>>3)+1,8) if _c == 0 else range(_s>>3)):
                _mask |= 1 << (_r*8+_f)
        FEATURE_PASSED[_c,_s] = np.uint64(_mask)


@njit(cache=False, inline='never')
def positional_features_nb(bb, st):
    features = np.zeros(24, dtype=np.int32)
    occ = st[OCC]
    for color in range(2):
        base = color*6
        enemy = (color^1)*6
        sign = 1 if color == 0 else -1
        pawns = bb[base]
        enemy_pawns = bb[enemy]
        king = lsb(bb[base+5])
        enemy_king = lsb(bb[enemy+5])
        own_att = np.uint64(0)
        scan = pawns
        while scan:
            sq = lsb(scan)
            scan &= scan-np.uint64(1)
            own_att |= PAWN_A[color,sq]
        enemy_att = np.uint64(0)
        scan = enemy_pawns
        while scan:
            sq = lsb(scan)
            scan &= scan-np.uint64(1)
            enemy_att |= PAWN_A[color^1,sq]
        for file in range(8):
            count = popc(pawns & FEATURE_FILES[file])
            if count > 1:
                features[1] += sign*(count-1)
            adjacent = np.uint64(0)
            if file > 0:
                adjacent |= FEATURE_FILES[file-1]
            if file < 7:
                adjacent |= FEATURE_FILES[file+1]
            if count and not (pawns & adjacent):
                features[0] += sign*count
        features[2] += sign*popc(own_att & pawns)
        scan = pawns
        while scan:
            sq = lsb(scan)
            scan &= scan-np.uint64(1)
            if not (enemy_pawns & FEATURE_PASSED[color,sq]):
                advance = (sq>>3) if color == 0 else 7-(sq>>3)
                features[3] += sign*advance
                push = sq+8 if color == 0 else sq-8
                if push < 0 or push >= 64 or (occ & bit(push)):
                    features[4] += sign
                features[5] += sign*max(abs((king&7)-(sq&7)),abs((king>>3)-(sq>>3)))
                features[6] += sign*max(abs((enemy_king&7)-(sq&7)),abs((enemy_king>>3)-(sq>>3)))
                features[17] += sign*max(0,advance-2)**2
        scan = bb[base+3]
        while scan:
            sq = lsb(scan)
            scan &= scan-np.uint64(1)
            file_mask = FEATURE_FILES[sq&7]
            if not (pawns & file_mask):
                features[7 if not (enemy_pawns & file_mask) else 8] += sign
            if (sq>>3) == (6 if color == 0 else 1):
                features[18] += sign
        for file in range(max(0,(king&7)-1),min(7,(king&7)+1)+1):
            for distance in range(1,3):
                rank = (king>>3)+(distance if color == 0 else -distance)
                if 0 <= rank < 8 and (pawns & bit(rank*8+file)):
                    features[9] += sign
                    break
        if not ((pawns | enemy_pawns) & FEATURE_FILES[king&7]):
            features[10] += sign
        if popc(bb[base+2]) >= 2:
            features[11] += sign
        safe = ~st[OCC_W if color == 0 else OCC_B] & ~enemy_att
        zone = KING_A[enemy_king] | bit(enemy_king)
        pressure = 0
        attackers = 0
        for pt in range(1,5):
            scan = bb[base+pt]
            while scan:
                sq = lsb(scan)
                scan &= scan-np.uint64(1)
                if pt == 1:
                    attacks = KNIGHT_A[sq]
                elif pt == 2:
                    attacks = bishop_att(sq,occ)
                elif pt == 3:
                    attacks = rook_att(sq,occ)
                else:
                    attacks = queen_att(sq,occ)
                features[11+pt] += sign*popc(attacks & safe)
                hits = popc(attacks & zone)
                if hits:
                    pressure += hits*(2 if pt <= 2 else (3 if pt == 3 else 5))
                    attackers += 1
        if bb[base+4]:
            features[16] += sign*pressure*min(3,attackers)
        for pt in range(5):
            features[19+pt] += sign*popc(bb[base+pt])
    return features


@njit(cache=False, inline='never')
def positional_correction_nb(bb, st):
    mg = 0
    eg = 0
    occ = st[OCC]
    for color in range(2):
        base = color*6
        enemy = (color^1)*6
        sign = 1 if color == 0 else -1
        pawns = bb[base]
        enemy_pawns = bb[enemy]
        king = lsb(bb[base+5])
        enemy_king = lsb(bb[enemy+5])
        own_att = np.uint64(0)
        scan = pawns
        while scan:
            sq = lsb(scan)
            scan &= scan-np.uint64(1)
            own_att |= PAWN_A[color,sq]
        enemy_att = np.uint64(0)
        scan = enemy_pawns
        while scan:
            sq = lsb(scan)
            scan &= scan-np.uint64(1)
            enemy_att |= PAWN_A[color^1,sq]
        for file in range(8):
            count = popc(pawns & FEATURE_FILES[file])
            if count > 1:
                mg += (sign*(count-1)) * (-14)
                eg += (sign*(count-1)) * (-6)
            adjacent = np.uint64(0)
            if file > 0:
                adjacent |= FEATURE_FILES[file-1]
            if file < 7:
                adjacent |= FEATURE_FILES[file+1]
            if count and not (pawns & adjacent):
                mg += (sign*count) * (-6)
                eg += (sign*count) * (-12)
        eg += (sign*popc(own_att & pawns)) * (8)
        scan = pawns
        while scan:
            sq = lsb(scan)
            scan &= scan-np.uint64(1)
            if not (enemy_pawns & FEATURE_PASSED[color,sq]):
                advance = (sq>>3) if color == 0 else 7-(sq>>3)
                mg += (sign*advance) * (6)
                eg += (sign*advance) * (8)
                push = sq+8 if color == 0 else sq-8
                if push < 0 or push >= 64 or (occ & bit(push)):
                    mg += (sign) * (-17)
                    eg += (sign) * (-38)
                mg += (sign*max(abs((king&7)-(sq&7)),abs((king>>3)-(sq>>3)))) * (-4)
                eg += (sign*max(abs((king&7)-(sq&7)),abs((king>>3)-(sq>>3)))) * (-5)
                eg += (sign*max(abs((enemy_king&7)-(sq&7)),abs((enemy_king>>3)-(sq>>3)))) * (5)
                eg += (sign*max(0,advance-2)**2) * (3)
        scan = bb[base+3]
        while scan:
            sq = lsb(scan)
            scan &= scan-np.uint64(1)
            file_mask = FEATURE_FILES[sq&7]
            if not (pawns & file_mask):
                mg += (sign) * (FEATURE_MG[7 if not (enemy_pawns & file_mask) else 8])
                eg += (sign) * (FEATURE_EG[7 if not (enemy_pawns & file_mask) else 8])
            if (sq>>3) == (6 if color == 0 else 1):
                eg += (sign) * (10)
        for file in range(max(0,(king&7)-1),min(7,(king&7)+1)+1):
            for distance in range(1,3):
                rank = (king>>3)+(distance if color == 0 else -distance)
                if 0 <= rank < 8 and (pawns & bit(rank*8+file)):
                    break
        if not ((pawns | enemy_pawns) & FEATURE_FILES[king&7]):
            mg += (sign) * (-59)
            eg += (sign) * (-7)
        if popc(bb[base+2]) >= 2:
            eg += (sign) * (72)
        safe = ~st[OCC_W if color == 0 else OCC_B] & ~enemy_att
        zone = KING_A[enemy_king] | bit(enemy_king)
        pressure = 0
        attackers = 0
        for pt in range(1,5):
            scan = bb[base+pt]
            while scan:
                sq = lsb(scan)
                scan &= scan-np.uint64(1)
                if pt == 1:
                    attacks = KNIGHT_A[sq]
                elif pt == 2:
                    attacks = bishop_att(sq,occ)
                elif pt == 3:
                    attacks = rook_att(sq,occ)
                else:
                    attacks = queen_att(sq,occ)
                mg += (sign*popc(attacks & safe)) * (FEATURE_MG[11+pt])
                eg += (sign*popc(attacks & safe)) * (FEATURE_EG[11+pt])
                hits = popc(attacks & zone)
                if hits:
                    pressure += hits*(2 if pt <= 2 else (3 if pt == 3 else 5))
                    attackers += 1
        if bb[base+4]:
            mg += (sign*pressure*min(3,attackers)) * (2)
            eg += (sign*pressure*min(3,attackers)) * (2)
        for pt in range(5):
            mg += (sign*popc(bb[base+pt])) * (FEATURE_MG[19+pt])
            eg += (sign*popc(bb[base+pt])) * (FEATURE_EG[19+pt])
    phase = min(24,np.int64(st[PHASE_ACC]))
    score = int(np.rint((mg*phase+eg*(24-phase))/24.0))
    return max(-400,min(400,score))


@njit(cache=False)
def evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc):
    phase = min(24, np.int64(st[PHASE_ACC])) / 24.0
    for piece in range(12):
        removed = nn_last[piece] & ~bb[piece]
        added = bb[piece] & ~nn_last[piece]
        for change in range(2):
            bits = removed if change == 0 else added
            sign = -1 if change == 0 else 1
            while bits:
                sq = lsb(bits)
                bits &= bits - np.uint64(1)
                white_idx = piece * 64 + sq
                black_idx = ((piece + 6) % 12) * 64 + (sq ^ 56)
                for j in range(net.shape[1]):
                    nn_acc[0,j] += sign * np.int32(net[white_idx,j])
                    nn_acc[1,j] += sign * np.int32(net[black_idx,j])
        nn_last[piece] = bb[piece]
    correction = 0.0
    for perspective in range(2):
        head = 769 if perspective == np.int32(st[SIDE]) else 771
        for j in range(net.shape[1]):
            act = min(2.0, max(0.0, nn_acc[perspective,j] / 4096.0))
            correction += act * (phase * net[head,j] + (1-phase)*net[head+1,j])
    score = pesto_nb(bb, st, True) + 400.0 * correction
    return np.int32(max(-30000.0, min(30000.0, score)))


@njit(cache=False)
def has_nm_pieces(bb, us):
    if us == 0:
        return (bb[1] | bb[2] | bb[3] | bb[4]) != np.uint64(0)
    return (bb[7] | bb[8] | bb[9] | bb[10]) != np.uint64(0)


@njit(cache=False)
def make_null(bb, mb, st, undo):
    undo[U_CAP] = np.uint64(12)
    undo[U_EP] = st[EP]
    undo[U_CASTLE] = st[CASTLE]
    undo[U_FIFTY] = st[FIFTY]
    undo[U_FULL] = st[FULL]
    undo[U_SIDE] = st[SIDE]
    undo[U_KEY] = st[KEY]
    ep = np.int32(st[EP])
    if ep != EP_NONE:
        if ep_hashable_nb(bb, mb, st):
            st[KEY] ^= Z_E[ep & 7]
        st[EP] = np.uint64(EP_NONE)
    us = np.int32(st[SIDE])
    st[KEY] ^= Z_S
    st[SIDE] ^= np.uint64(1)
    # Null moves are an internal pruning device, not referee plies.  They
    # must not fabricate a rule-50 claim (nor advance the cap, handled by the
    # caller's unchanged ``cap_left``).
    if us == 1:
        st[FULL] += np.uint64(1)


@njit(cache=False)
def unmake_null(st, undo):
    st[EP] = undo[U_EP]
    st[CASTLE] = undo[U_CASTLE]
    st[FIFTY] = undo[U_FIFTY]
    st[FULL] = undo[U_FULL]
    st[SIDE] = undo[U_SIDE]
    st[KEY] = undo[U_KEY]


@njit(cache=False)
def perft_nb(bb, mb, st, depth):
    if depth == 0:
        return 1
    moves = np.empty(MAX_MOVES, dtype=np.int32)
    scratch = np.empty(MAX_MOVES, dtype=np.int32)
    n = gen_legal(bb, mb, st, moves, scratch)
    if depth == 1:
        return n
    nodes = 0
    for i in range(n):
        u = np.zeros(7, dtype=np.uint64)
        make_nb(bb, mb, st, moves[i], u)
        nodes += perft_nb(bb, mb, st, depth - 1)
        unmake_nb(bb, mb, st, moves[i], u)
    return nodes


@njit(cache=False)
def tt_to(score, ply):
    if score >= MATE_WIN:
        return score + ply
    if score <= -MATE_WIN:
        return score - ply
    return score


@njit(cache=False)
def tt_from(score, ply):
    if score >= MATE_WIN:
        return score - ply
    if score <= -MATE_WIN:
        return score + ply
    return score


@njit(cache=False)
def cap_tt_key(key, cap_left):
    if cap_left > MAX_PLY:
        return np.uint64(key)
    mixed = np.uint64(key) ^ (np.uint64(cap_left + 1) * np.uint64(0xC2B2AE3D27D4EB4F))
    return np.uint64(1) if mixed == 0 else mixed


@njit(cache=False)
def tt_probe(key, ply, ttk, ttm, tts, ttd, ttg):
    idx = np.int64(np.uint64(key) & np.uint64(TT_MASK))
    if ttk[idx] != np.uint64(key) or ttk[idx] == 0:
        return False, np.int32(0), np.int32(0), np.int32(0), np.int32(0)
    raw = np.int32(tts[idx])
    return True, ttm[idx], np.int32(ttd[idx]), np.int32(ttg[idx]) & 3, tt_from(raw, ply)


@njit(cache=False)
def tt_store(key, move, depth, flag, score, ply, ttk, ttm, tts, ttd, ttg, tta):
    if key == 0:
        return
    idx = np.int64(np.uint64(key) & np.uint64(TT_MASK))
    age = tta[0]
    if ttk[idx] == np.uint64(key) and (np.int32(ttg[idx]) >> 2) == age and np.int32(ttd[idx]) > depth:
        return
    if ttk[idx] == np.uint64(key) and move == 0:
        move = ttm[idx]
    packed = tt_to(score, ply)
    if packed > 32767:
        packed = 32767
    elif packed < -32768:
        packed = -32768
    if depth > 255:
        depth = 255
    ttk[idx] = np.uint64(key)
    ttm[idx] = move
    tts[idx] = np.int16(packed)
    ttd[idx] = np.uint8(depth)
    ttg[idx] = np.uint8((age << 2) | (flag & 3))


@njit(cache=False)
def is_repeat(key, hist, hlen):
    for i in range(hlen):
        if hist[i] == np.uint64(key):
            return True
    return False


@njit(cache=False)
def victim_pt(mb, move):
    if m_ep(move):
        return 0
    cap = np.int32(mb[m_to(move)])
    if cap >= 0:
        return cap % 6
    return 0


@njit(cache=False)
def lva(bb, mb, to, side, occ):
    base = 0 if side == 0 else 6
    b = PAWN_A[side ^ 1, to] & bb[base] & occ
    if b:
        return lsb(b)
    b = KNIGHT_A[to] & bb[base + 1] & occ
    if b:
        return lsb(b)
    bq = bishop_att(to, occ) & occ
    b = bq & bb[base + 2]
    if b:
        return lsb(b)
    rq = rook_att(to, occ) & occ
    b = rq & bb[base + 3]
    if b:
        return lsb(b)
    b = (bq | rq) & bb[base + 4]
    if b:
        return lsb(b)
    b = KING_A[to] & bb[base + 5] & occ
    if b:
        return lsb(b)
    return np.int32(-1)


@njit(cache=False)
def legal_lva_see_nb(work, to, side, occ, victim):
    """Least valuable *legal* recapture onto ``to``.

    A geometric attacker may be absolutely pinned, and a king may not capture
    onto an attacked square.  Trial bitboards are local to SEE only; this is
    still a bounded native swap-off, not legal-tree generation in qsearch.
    """
    base = side * 6
    bq = bishop_att(to, occ)
    rq = rook_att(to, occ)
    for typ in range(6):
        if typ == 0:
            candidates = PAWN_A[side ^ 1, to] & work[base]
        elif typ == 1:
            candidates = KNIGHT_A[to] & work[base + 1]
        elif typ == 2:
            candidates = bq & work[base + 2]
        elif typ == 3:
            candidates = rq & work[base + 3]
        elif typ == 4:
            candidates = (bq | rq) & work[base + 4]
        else:
            candidates = KING_A[to] & work[base + 5]
        candidates &= occ
        while candidates:
            frm = lsb(candidates)
            candidates &= candidates - np.uint64(1)
            promoted = typ == 0 and ((side == 0 and to >= 56) or (side == 1 and to < 8))
            moved = base + (4 if promoted else typ)
            trial = np.empty(12, dtype=np.uint64)
            for j in range(12):
                trial[j] = work[j]
            trial[victim] &= ~bit(to)
            trial[base + typ] &= ~bit(frm)
            trial[moved] |= bit(to)
            occ_after = occ & ~bit(frm)
            occ_after |= bit(to)
            king = trial[base + 5]
            if king and not sq_attacked(trial, lsb(king), side ^ 1, occ_after):
                bonus = SEE_V[4] - SEE_V[0] if promoted else 0
                return frm, np.int32(base + typ), np.int32(moved), np.int32(bonus)
    return np.int32(-1), np.int32(-1), np.int32(-1), np.int32(0)


@njit(cache=False)
def see_nb(bb, mb, st, move):
    """Legality-aware static exchange evaluation in centipawns.

    The old helper only removed geometric attackers from occupancy.  It could
    therefore invent a king recapture onto an attacked square or a recapture
    by an absolutely pinned piece, causing qsearch to prune a free pawn.
    """
    frm = m_from(move)
    to = m_to(move)
    us = np.int32(st[SIDE])
    mover = np.int32(mb[frm])
    if mover < 0:
        return 0
    work = np.empty(12, dtype=np.uint64)
    for i in range(12):
        work[i] = bb[i]
    occ = np.uint64(st[OCC])
    promo = m_promo(move)
    if m_ep(move):
        cap_sq = to - 8 if us == 0 else to + 8
        cap = 6 if us == 0 else 0
        work[cap] &= ~bit(cap_sq)
        occ &= ~bit(cap_sq)
        gain = SEE_V[0]
    else:
        cap = np.int32(mb[to])
        gain = SEE_V[cap % 6] if cap >= 0 else 0
        if cap >= 0:
            work[cap] &= ~bit(to)
    if promo:
        gain += SEE_V[promo] - SEE_V[0]
    work[mover] &= ~bit(frm)
    moved = us * 6 + promo if promo else mover
    work[moved] |= bit(to)
    occ &= ~bit(frm)
    occ |= bit(to)
    victim = np.int32(moved)
    hanging = SEE_V[victim % 6]
    side = us ^ 1
    gains = np.empty(32, dtype=np.int32)
    gains[0] = gain
    ng = 1
    while ng < 32:
        att, piece, moved, bonus = legal_lva_see_nb(work, to, side, occ, victim)
        if att < 0:
            break
        gains[ng] = hanging + bonus - gains[ng - 1]
        work[victim] &= ~bit(to)
        work[piece] &= ~bit(att)
        work[moved] |= bit(to)
        occ &= ~bit(att)
        occ |= bit(to)
        victim = moved
        hanging = SEE_V[victim % 6]
        ng += 1
        if hanging == SEE_V[5]:
            break
        side ^= 1
    i = ng - 1
    while i > 0:
        left = -gains[i - 1]
        right = gains[i]
        mx = left if left > right else right
        gains[i - 1] = -mx
        i -= 1
    return gains[0]


@njit(cache=False)
def order_key(mb, move, ply, hash_move, killers, histy):
    if hash_move and move == hash_move:
        return np.int32(0), np.int32(0)
    if m_cap(move) or m_promo(move):
        att = np.int32(mb[m_from(move)])
        vic = victim_pt(mb, move)
        att_pt = att % 6 if att >= 0 else 0
        gain = SEE_V[vic] if m_cap(move) else 0
        promo = m_promo(move)
        if promo:
            gain += SEE_V[promo] - SEE_V[0]
        return np.int32(1), np.int32(-(gain * 16 - SEE_V[att_pt]))
    if ply < MAX_PLY and killers[ply, 0] == move:
        return np.int32(2), np.int32(0)
    if ply < MAX_PLY and killers[ply, 1] == move:
        return np.int32(3), np.int32(0)
    p = np.int32(mb[m_from(move)])
    h = -histy[p, m_to(move)] if p >= 0 else 0
    return np.int32(4), np.int32(h)


@njit(cache=False)
def sort_moves(mb, moves, n, ply, hash_move, killers, histy):
    if n <= 1:
        return
    keys0 = np.empty(n, dtype=np.int32)
    keys1 = np.empty(n, dtype=np.int32)
    for i in range(n):
        a, b = order_key(mb, moves[i], ply, hash_move, killers, histy)
        keys0[i] = a
        keys1[i] = b
    for i in range(1, n):
        mv = moves[i]
        k0 = keys0[i]
        k1 = keys1[i]
        j = i
        while j > 0 and (keys0[j - 1] > k0 or (keys0[j - 1] == k0 and keys1[j - 1] > k1)):
            moves[j] = moves[j - 1]
            keys0[j] = keys0[j - 1]
            keys1[j] = keys1[j - 1]
            j -= 1
        moves[j] = mv
        keys0[j] = k0
        keys1[j] = k1


@njit(cache=False)
def history_update(histy, piece, to, bonus):
    """Bounded gravity lets recent failures erase old successes."""
    bonus = min(HISTORY_MAX, max(-HISTORY_MAX, bonus))
    old = histy[piece, to]
    histy[piece, to] = old + bonus - old * abs(bonus) // HISTORY_MAX


@njit(cache=False)
def cutoff_quiet(mb, move, depth, ply, killers, histy):
    if m_cap(move) or m_promo(move) or ply >= MAX_PLY:
        return
    if killers[ply, 0] != move:
        killers[ply, 1] = killers[ply, 0]
        killers[ply, 0] = move
    p = np.int32(mb[m_from(move)])
    if p < 0:
        return
    history_update(histy, p, m_to(move), min(1600, 32 * depth * depth))


@njit(cache=False)
def quiet_reduction(depth, searched, is_pv, history_score):
    """The caller excludes checks, tactical moves, killers and advanced pawns."""
    if depth < LMR_MIN_D or searched < 3 + int(is_pv):
        return 0
    reduction = LMR_TABLE[min(depth, MAX_DEPTH), min(searched + 1, MAX_MOVES)]
    if is_pv:
        reduction -= 1
    if history_score > 4000:
        reduction -= 1
    elif history_score < -4000:
        reduction += 1
    return max(0, min(depth - 2, reduction))


@njit(cache=False)
def check_clock(nodes, max_nodes, allow_abort, aborted):
    if not allow_abort:
        return False
    if nodes[0] >= max_nodes:
        aborted[0] = 1
        return True
    # The node budget remains useful to deterministic lab probes. Live search
    # has a real monotonic deadline: changing branching factors cannot spend
    # more wall time than forecast. One Python clock call per 1024 nodes.
    if nodes.size > 1 and nodes[1] > 0 and (nodes[0] & 1023) == 0:
        with objmode(now_ns="int64"):
            now_ns = time.perf_counter_ns()
        if now_ns >= nodes[1]:
            aborted[0] = 1
            return True
    return False


@njit(cache=False)
def qsearch_nb(
    bb,
    mb,
    st,
    alpha,
    beta,
    ply,
    hist,
    hlen,
    adjudicate, cap_left,
    max_nodes,
    allow_abort,
    undos,
    stacks,
    scratches,
    ttk,
    ttm,
    tts,
    ttd,
    ttg,
    tta,
    killers,
    histy,
    net,
    nn_last,
    nn_acc,
    nodes,
    aborted,
):
    nodes[0] += 1
    if check_clock(nodes, max_nodes, allow_abort, aborted):
        return 0
    if cap_left <= 0:
        checked_at_cap = in_check_nb(bb, st, np.int32(st[SIDE]))
        cap_moves = np.empty(MAX_MOVES, dtype=np.int32) if ply >= MAX_PLY else stacks[ply]
        cap_scratch = np.empty(MAX_MOVES, dtype=np.int32) if ply >= MAX_PLY else scratches[ply]
        legal_at_cap = gen_legal(bb, mb, st, cap_moves, cap_scratch)
        if legal_at_cap == 0 and checked_at_cap:
            return np.int32(-MATE + ply)
        return DRAW

    if ply >= MAX_PLY:
        return evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc)

    moves_buf = stacks[ply]
    scratch = scratches[ply]
    checked = in_check_nb(bb, st, np.int32(st[SIDE]))
    nlegal = -1
    repeated = is_repeat(st[KEY], hist, hlen)
    if repeated or np.int32(st[FIFTY]) >= 100:
        if np.int32(st[FIFTY]) >= 100 or checked:
            nlegal = gen_legal(bb, mb, st, moves_buf, scratch)
            if nlegal == 0:
                return np.int32(-MATE + ply) if checked else DRAW
        if repeated:
            return DRAW
        if fifty_claim_nb(bb, mb, st, moves_buf, nlegal, scratch, undos[ply]):
            return DRAW
    if insufficient_material_nb(bb):
        return DRAW
    orig_alpha = alpha
    hash_move = np.int32(0)
    if not adjudicate:
        hit, move, _d, flag, s = tt_probe(cap_tt_key(st[KEY], cap_left), ply, ttk, ttm, tts, ttd, ttg)
        if hit:
            hash_move = move
            if flag == EXACT:
                return s
            if flag == LOWER and s >= beta:
                return s
            if flag == UPPER and s <= alpha:
                return s

    if not checked:
        stand = evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc)
        if nn_acc[2,1]:
            nn_acc[2,0]+=1
            if nn_acc[2,0]%257==0:
                row=3+(nn_acc[2,0]//257)%64
                for piece in range(12):
                    nn_acc[row,2*piece]=np.int32(bb[piece]&np.uint64(0xffffffff))
                    nn_acc[row,2*piece+1]=np.int32(bb[piece]>>np.uint64(32))
                nn_acc[row,24]=np.int32(st[SIDE])
                nn_acc[row,25]=np.int32(st[CASTLE])
                nn_acc[row,26]=np.int32(st[EP])
                nn_acc[row,27]=np.int32(st[FIFTY])
                nn_acc[row,28]=np.int32(st[FULL])
                nn_acc[row,29]=stand
                nn_acc[row,30]=ply
                nn_acc[row,31]=beta

        if stand >= beta:
            if popc(st[OCC]) <= STALEMATE_SCAN_MAX_PIECES and not has_legal_nb(
                bb, mb, st, scratch, undos[ply]
            ):
                return DRAW
            if not adjudicate:
                tt_store(cap_tt_key(st[KEY], cap_left), 0, 0, LOWER, stand, ply, ttk, ttm, tts, ttd, ttg, tta)
            return stand
        if stand > alpha:
            alpha = stand
        n = gen_noisy(bb, mb, st, moves_buf, scratch)
        if (
            n == 0
            and popc(st[OCC]) <= STALEMATE_SCAN_MAX_PIECES
            and not has_legal_nb(bb, mb, st, scratch, undos[ply])
        ):
            return DRAW
        best = stand
    else:
        stand = 0
        n = nlegal if nlegal >= 0 else gen_legal(bb, mb, st, moves_buf, scratch)
        if n == 0:
            return np.int32(-MATE + ply)
        best = -INF

    sort_moves(mb, moves_buf, n, ply, hash_move, killers, histy)
    best_move = np.int32(0)
    hist[hlen] = st[KEY]
    hlen2 = hlen + 1
    for i in range(n):
        move = moves_buf[i]
        if not checked:
            promo = m_promo(move)
            cap_v = SEE_V[victim_pt(mb, move)]
            if promo:
                cap_v += SEE_V[promo] - SEE_V[0]
            delta_bad = stand + cap_v + DELTA < alpha
            see_bad = move != hash_move and see_nb(bb, mb, st, move) < 0
            if (delta_bad or see_bad) and not gives_check_nb(
                bb, mb, st, move, undos[ply]
            ):
                continue
        make_nb(bb, mb, st, move, undos[ply])
        score = -qsearch_nb(
            bb,
            mb,
            st,
            -beta,
            -alpha,
            ply + 1,
            hist,
            hlen2,
            adjudicate, cap_left - 1,
            max_nodes,
            allow_abort,
            undos,
            stacks,
            scratches,
            ttk,
            ttm,
            tts,
            ttd,
            ttg,
            tta,
            killers,
            histy,
            net,
            nn_last,
            nn_acc,
            nodes,
            aborted,
        )
        unmake_nb(bb, mb, st, move, undos[ply])
        if aborted[0]:
            return 0
        if score > best:
            best = score
            best_move = move
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    if not adjudicate:
        flag = EXACT
        if best <= orig_alpha:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        tt_store(cap_tt_key(st[KEY], cap_left), best_move, 0, flag, best, ply, ttk, ttm, tts, ttd, ttg, tta)
    return best


@njit(cache=False)
def negamax_nb(
    bb,
    mb,
    st,
    depth,
    alpha,
    beta,
    ply,
    hist,
    hlen,
    adjudicate, cap_left,
    max_nodes,
    allow_abort,
    undos,
    stacks,
    scratches,
    ttk,
    ttm,
    tts,
    ttd,
    ttg,
    tta,
    killers,
    histy,
    net,
    nn_last,
    nn_acc,
    nodes,
    aborted,
):
    nodes[0] += 1
    if check_clock(nodes, max_nodes, allow_abort, aborted):
        return 0
    if cap_left <= 0:
        checked_at_cap = in_check_nb(bb, st, np.int32(st[SIDE]))
        cap_moves = np.empty(MAX_MOVES, dtype=np.int32) if ply >= MAX_PLY else stacks[ply]
        cap_scratch = np.empty(MAX_MOVES, dtype=np.int32) if ply >= MAX_PLY else scratches[ply]
        legal_at_cap = gen_legal(bb, mb, st, cap_moves, cap_scratch)
        if legal_at_cap == 0 and checked_at_cap:
            return np.int32(-MATE + ply)
        return DRAW

    if ply >= MAX_PLY:
        return evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc)

    checked = in_check_nb(bb, st, np.int32(st[SIDE]))
    moves_buf = stacks[ply]
    scratch = scratches[ply]
    nlegal = -1
    repeated = is_repeat(st[KEY], hist, hlen)
    if repeated or np.int32(st[FIFTY]) >= 100:
        if np.int32(st[FIFTY]) >= 100 or checked:
            nlegal = gen_legal(bb, mb, st, moves_buf, scratch)
            if nlegal == 0:
                return np.int32(-MATE + ply) if checked else DRAW
        if repeated:
            return DRAW
        if fifty_claim_nb(bb, mb, st, moves_buf, nlegal, scratch, undos[ply]):
            return DRAW
    if insufficient_material_nb(bb):
        return DRAW
    if checked and ply < CHECK_EXT_PLY and depth < 32:
        depth += 1
    if depth <= 0:
        return qsearch_nb(
            bb,
            mb,
            st,
            alpha,
            beta,
            ply,
            hist,
            hlen,
            adjudicate, cap_left,
            max_nodes,
            allow_abort,
            undos,
            stacks,
            scratches,
            ttk,
            ttm,
            tts,
            ttd,
            ttg,
            tta,
            killers,
            histy,
            net,
            nn_last,
            nn_acc,
            nodes,
            aborted,
        )

    mate_alpha = np.int32(-MATE + ply)
    mate_beta = np.int32(MATE - ply - 1)
    if alpha < mate_alpha:
        alpha = mate_alpha
    if beta > mate_beta:
        beta = mate_beta
    if alpha >= beta:
        return alpha

    is_pv = (beta - alpha) > 1
    orig_alpha = alpha
    hash_move = np.int32(0)
    if not adjudicate:
        hit, move, tdepth, flag, s = tt_probe(cap_tt_key(st[KEY], cap_left), ply, ttk, ttm, tts, ttd, ttg)
        if hit:
            hash_move = move
            if tdepth >= depth:
                if flag == EXACT:
                    return s
                if (not is_pv) and flag == LOWER and s >= beta:
                    return s
                if (not is_pv) and flag == UPPER and s <= alpha:
                    return s

    static_eval = 0
    if not checked:
        static_eval = evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc)
        if (
            (not is_pv)
            and (not adjudicate)
            and depth <= RFP_MAX_D
            and beta > -MATE_WIN
            and beta < MATE_WIN
            and static_eval >= beta + RFP_MARGIN * depth
        ):
            return static_eval
        if (
            (not is_pv)
            and (not adjudicate)
            and depth >= NMP_MIN_D
            and static_eval >= beta
            and -MATE_WIN < beta < MATE_WIN
            and (ply == 0 or undos[ply - 1, U_CAP] != np.uint64(13))
            and np.int32(st[FIFTY]) < 90
            and has_nm_pieces(bb, np.int32(st[SIDE]))
        ):
            r = 2 + depth // 5 + min(2, (static_eval - beta) // 200)
            make_null(bb, mb, st, undos[ply])
            # Legal make uses captured-piece IDs 0..11 or empty=12.
            # This slot is ignored by unmake_null and marks only this edge.
            undos[ply, U_CAP] = np.uint64(13)
            score = -negamax_nb(
                bb,
                mb,
                st,
                depth - 1 - r,
                -beta,
                -beta + 1,
                ply + 1,
                hist,
                hlen,
                adjudicate, cap_left,
                max_nodes,
                allow_abort,
                undos,
                stacks,
                scratches,
                ttk,
                ttm,
                tts,
                ttd,
                ttg,
                tta,
                killers,
                histy,
                net,
                nn_last,
                nn_acc,
                nodes,
                aborted,
            )
            unmake_null(st, undos[ply])
            if aborted[0]:
                return 0
            if score >= beta:
                if score >= MATE_WIN:
                    return beta
                return score

    if hash_move == 0 and depth >= IIR_MIN_D and not checked and not adjudicate:
        depth -= 1

    n = nlegal if nlegal >= 0 else gen_legal(bb, mb, st, moves_buf, scratch)
    if n == 0:
        if checked:
            return np.int32(-MATE + ply)
        return DRAW

    sort_moves(mb, moves_buf, n, ply, hash_move, killers, histy)
    hist[hlen] = st[KEY]
    hlen2 = hlen + 1
    best = -INF
    best_move = np.int32(0)
    searched = 0
    # Legal generation has finished using this ply's scratch; reuse it for
    # quiet losers instead of allocating another array at every node.
    quiets_searched = scratch
    nquiets = 0
    for i in range(n):
        move = moves_buf[i]
        quiet = not (m_cap(move) or m_promo(move))
        mover = np.int32(mb[m_from(move)])
        move_history = histy[mover, m_to(move)] if quiet else 0
        if (
            (not is_pv)
            and (not checked)
            and (not adjudicate)
            and quiet
            and depth <= FF_MAX_D
            and static_eval + FF_MARGIN * depth <= alpha
            and move != hash_move
            and not gives_check_nb(bb, mb, st, move, undos[ply])
        ):
            continue
        if (
            (not is_pv)
            and (not checked)
            and (not adjudicate)
            and (not quiet)
            and not m_promo(move)
            and depth <= SEE_PRUNE_MAX_D
            and move != hash_move
            and see_nb(bb, mb, st, move) < -SEE_PRUNE_MARGIN * depth
            and not gives_check_nb(bb, mb, st, move, undos[ply])
        ):
            continue
        make_nb(bb, mb, st, move, undos[ply])
        child_d = depth - 1
        reduction = 0
        advanced_pawn = mover % 6 == 0 and (
            (mover == 0 and m_to(move) >= 40) or (mover == 6 and m_to(move) < 24)
        )
        if (
            quiet
            and depth >= LMR_MIN_D
            and searched >= 3 + int(is_pv)
            and not checked
            and not adjudicate
            and not advanced_pawn
            and move != hash_move
            and move != killers[ply, 0]
            and move != killers[ply, 1]
            and not in_check_nb(bb, st, np.int32(st[SIDE]))
        ):
            reduction = quiet_reduction(depth, searched, is_pv, move_history)
        if searched == 0:
            score = -negamax_nb(
                bb,
                mb,
                st,
                child_d,
                -beta,
                -alpha,
                ply + 1,
                hist,
                hlen2,
                adjudicate, cap_left - 1,
                max_nodes,
                allow_abort,
                undos,
                stacks,
                scratches,
                ttk,
                ttm,
                tts,
                ttd,
                ttg,
                tta,
                killers,
                histy,
                net,
                nn_last,
                nn_acc,
                nodes,
                aborted,
            )
        else:
            score = -negamax_nb(
                bb,
                mb,
                st,
                child_d - reduction,
                -alpha - 1,
                -alpha,
                ply + 1,
                hist,
                hlen2,
                adjudicate, cap_left - 1,
                max_nodes,
                allow_abort,
                undos,
                stacks,
                scratches,
                ttk,
                ttm,
                tts,
                ttd,
                ttg,
                tta,
                killers,
                histy,
                net,
                nn_last,
                nn_acc,
                nodes,
                aborted,
            )
            # A reduced fail-high is a question, never a cutoff. Verify at
            # the original depth before trusting it or opening the PV window.
            if reduction and not aborted[0] and score > alpha:
                score = -negamax_nb(
                    bb,
                    mb,
                    st,
                    child_d,
                    -alpha - 1,
                    -alpha,
                    ply + 1,
                    hist,
                    hlen2,
                    adjudicate, cap_left - 1,
                    max_nodes,
                    allow_abort,
                    undos,
                    stacks,
                    scratches,
                    ttk,
                    ttm,
                    tts,
                    ttd,
                    ttg,
                    tta,
                    killers,
                    histy,
                    net,
                    nn_last,
                    nn_acc,
                    nodes,
                    aborted,
                )
            if (not aborted[0]) and score > alpha and score < beta:
                score = -negamax_nb(
                    bb,
                    mb,
                    st,
                    child_d,
                    -beta,
                    -alpha,
                    ply + 1,
                    hist,
                    hlen2,
                    adjudicate, cap_left - 1,
                    max_nodes,
                    allow_abort,
                    undos,
                    stacks,
                    scratches,
                    ttk,
                    ttm,
                    tts,
                    ttd,
                    ttg,
                    tta,
                    killers,
                    histy,
                    net,
                    nn_last,
                    nn_acc,
                    nodes,
                    aborted,
                )
        unmake_nb(bb, mb, st, move, undos[ply])
        if aborted[0]:
            return 0
        searched += 1
        if score > best:
            best = score
            best_move = move
        if best > alpha:
            alpha = best
        if alpha >= beta:
            cutoff_quiet(mb, move, depth, ply, killers, histy)
            if quiet:
                malus = -min(1600, 32 * depth * depth)
                for q in range(nquiets):
                    failed_move = quiets_searched[q]
                    failed_piece = np.int32(mb[m_from(failed_move)])
                    history_update(histy, failed_piece, m_to(failed_move), malus)
            break
        if quiet:
            quiets_searched[nquiets] = move
            nquiets += 1
    # Forward futility or SEE pruning can skip every legal move.  That is a
    # fail-low, not a mate: never turn the uninitialised -INF sentinel into a
    # transposition-table score.
    if best_move == 0:
        return orig_alpha
    if not adjudicate:
        flag = EXACT
        if best <= orig_alpha:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        tt_store(cap_tt_key(st[KEY], cap_left), best_move, depth, flag, best, ply, ttk, ttm, tts, ttd, ttg, tta)
    return best


@njit(cache=False)
def root_search_nb(
    bb,
    mb,
    st,
    root_moves,
    nroot,
    depth,
    hist,
    hlen,
    pv,
    alpha,
    beta,
    adjudicate, cap_left,
    max_nodes,
    undos,
    stacks,
    scratches,
    ttk,
    ttm,
    tts,
    ttd,
    ttg,
    tta,
    killers,
    histy,
    net,
    nn_last,
    nn_acc,
    nodes,
    aborted,
):
    moves = stacks[0]
    for i in range(nroot):
        moves[i] = root_moves[i]
    sort_moves(mb, moves, nroot, 0, pv, killers, histy)
    best_move = moves[0]
    best_score = -INF
    hist[hlen] = st[KEY]
    hlen2 = hlen + 1
    for i in range(nroot):
        allow = True
        move = moves[i]
        make_nb(bb, mb, st, move, undos[0])
        child_d = depth - 1
        if i == 0:
            score = -negamax_nb(
                bb,
                mb,
                st,
                child_d,
                -beta,
                -alpha,
                1,
                hist,
                hlen2,
                adjudicate, cap_left - 1,
                max_nodes,
                allow,
                undos,
                stacks,
                scratches,
                ttk,
                ttm,
                tts,
                ttd,
                ttg,
                tta,
                killers,
                histy,
                net,
                nn_last,
                nn_acc,
                nodes,
                aborted,
            )
        else:
            score = -negamax_nb(
                bb,
                mb,
                st,
                child_d,
                -alpha - 1,
                -alpha,
                1,
                hist,
                hlen2,
                adjudicate, cap_left - 1,
                max_nodes,
                allow,
                undos,
                stacks,
                scratches,
                ttk,
                ttm,
                tts,
                ttd,
                ttg,
                tta,
                killers,
                histy,
                net,
                nn_last,
                nn_acc,
                nodes,
                aborted,
            )
            if (not aborted[0]) and score > alpha and score < beta:
                score = -negamax_nb(
                    bb,
                    mb,
                    st,
                    child_d,
                    -beta,
                    -alpha,
                    1,
                    hist,
                    hlen2,
                    adjudicate, cap_left - 1,
                    max_nodes,
                    allow,
                    undos,
                    stacks,
                    scratches,
                    ttk,
                    ttm,
                    tts,
                    ttd,
                    ttg,
                    tta,
                    killers,
                    histy,
                    net,
                    nn_last,
                    nn_acc,
                    nodes,
                    aborted,
                )
        unmake_nb(bb, mb, st, move, undos[0])
        if aborted[0]:
            break
        if score > best_score:
            best_score = score
            best_move = move
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best_move, best_score


def pack_pos(pos):
    bb = np.array(pos.bb, dtype=np.uint64)
    mb = np.array(pos.mb, dtype=np.int8)
    st = np.zeros(12, dtype=np.uint64)
    st[OCC_W] = np.uint64(pos.occ_w)
    st[OCC_B] = np.uint64(pos.occ_b)
    st[OCC] = np.uint64(pos.occ)
    st[SIDE] = np.uint64(pos.side)
    st[CASTLE] = np.uint64(pos.castle)
    st[EP] = np.uint64(pos.ep)
    st[FIFTY] = np.uint64(pos.fifty)
    st[FULL] = np.uint64(pos.fullmove)
    st[KEY] = np.uint64(pos.key)
    mg = eg = phase = 0
    for sq, piece in enumerate(pos.mb):
        if piece >= 0:
            sign = 1 if piece < 6 else -1
            mg += sign * int(MG_T[piece, sq])
            eg += sign * int(EG_T[piece, sq])
            phase += int(PHASE_INC[piece % 6])
    st[MG_ACC] = np.uint64(mg & ((1 << 64) - 1))
    st[EG_ACC] = np.uint64(eg & ((1 << 64) - 1))
    st[PHASE_ACC] = np.uint64(phase)
    return bb, mb, st


def perft_pos(pos, depth: int) -> int:
    bb, mb, st = pack_pos(pos)
    return int(perft_nb(bb, mb, st, depth))


_LAST_NODES = 0
_LAST_INFO = {}


def iteration_node_limit(
    nodes_before: int, remaining_ms: float, last_nps: float, depth: int
) -> int:
    """Convert one ID pass's allowance to the cumulative stop counter."""
    if depth <= 1:
        return 10**15
    allowance = int(max(8000.0, (remaining_ms / 1000.0) * last_nps * 0.85))
    return nodes_before + allowance


def search_root(pos, packed_root, hard_ms, soft_ms, adjudicate, game_zkeys) -> int:
    """Storm ID: completed-iteration evidence controls a real wall deadline."""
    global _LAST_NODES, _LAST_INFO
    from storm_clock import SearchClock

    adjudicate = False
    start = time.perf_counter()
    bb, mb, st = pack_pos(pos)
    root = np.array(packed_root, dtype=np.int32)
    z = game_zkeys[:-1] if game_zkeys else []
    zkeys = np.array(z, dtype=np.uint64) if z else np.zeros(0, dtype=np.uint64)
    nodes = np.zeros(2, dtype=np.int64)
    nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)
    aborted = np.zeros(1, dtype=np.int32)
    if not adjudicate:
        TT_AGE[0] = np.int32((int(TT_AGE[0]) + 1) & 63)
        if TT_AGE[0] == 0:
            TT_AGE[0] = np.int32(1)
    KILLERS.fill(0)
    hlen = len(zkeys)
    hist = np.empty(hlen + MAX_PLY + 8, dtype=np.uint64)
    for i in range(hlen):
        hist[i] = zkeys[i]
    undos = np.zeros((MAX_PLY, 7), dtype=np.uint64)
    stacks = np.zeros((MAX_PLY, MAX_MOVES), dtype=np.int32)
    scratches = np.zeros((MAX_PLY, MAX_MOVES), dtype=np.int32)
    best = int(root[0])
    prev = 0
    adj = 0
    cap_left = max(0, 600 - (2 * (int(pos.fullmove) - 1) + int(pos.side)))
    nroot = len(packed_root)
    controller = SearchClock(soft_ms, hard_ms, root_moves=nroot)
    completed_depth = 0
    trace = []

    for depth in range(1, MAX_DEPTH + 1):
        now = time.perf_counter()
        elapsed_ms = (now - start) * 1000.0
        remaining_ms = hard_ms - elapsed_ms
        if remaining_ms < 5.0:
            break
        if depth > 1 and not controller.should_start(elapsed_ms):
            break
        nodes_before = int(nodes[0])
        max_nodes = 10**15  # deadline inside compiled search is authoritative
        aborted[0] = 0
        if depth <= 3:
            a = -INF
            b = INF
        else:
            a = prev - ASPIRATION
            b = prev + ASPIRATION
        args = (
            bb,
            mb,
            st,
            root,
            nroot,
            depth,
            hist,
            hlen,
            best,
            a,
            b,
            adj, cap_left,
            max_nodes,
            undos,
            stacks,
            scratches,
            TT_KEY,
            TT_MOVE,
            TT_SCORE,
            TT_DEPTH,
            TT_GEN,
            TT_AGE,
            KILLERS,
            HISTORY, NET, NN_LAST_BB, NN_ACC,
            nodes,
            aborted,
        )
        move, score = root_search_nb(*args)
        aspiration_failed = not aborted[0] and (score <= a or score >= b)
        if aspiration_failed:
            args = (
                bb,
                mb,
                st,
                root,
                nroot,
                depth,
                hist,
                hlen,
                best,
                -INF,
                INF,
                adj, cap_left,
                max_nodes,
                undos,
                stacks,
                scratches,
                TT_KEY,
                TT_MOVE,
                TT_SCORE,
                TT_DEPTH,
                TT_GEN,
                TT_AGE,
                KILLERS,
                HISTORY, NET, NN_LAST_BB, NN_ACC,
                nodes,
                aborted,
            )
            move, score = root_search_nb(*args)
        dt = time.perf_counter() - now
        dn = int(nodes[0]) - nodes_before
        if aborted[0]:
            break
        best = int(move)
        prev = int(score)
        completed_depth = depth
        controller.complete(depth, best, prev, dt * 1000.0, dn,
                            aspiration_failed=bool(aspiration_failed))
        trace.append((depth, best, prev, dn, round(dt * 1000.0, 2), bool(aspiration_failed)))
    _LAST_NODES = int(nodes[0])
    _LAST_INFO = {"depth": completed_depth, "score": prev, "nodes": _LAST_NODES,
                  "elapsed_ms": (time.perf_counter() - start) * 1000.0,
                  "target_ms": controller.target_ms, "hard_ms": hard_ms,
                  "aborted": bool(aborted[0]), "trace": trace}
    return best


def last_nodes() -> int:
    return _LAST_NODES


def last_info() -> dict:
    return dict(_LAST_INFO)


def probe_move(key: int) -> int:
    hit, move, _d, _flag, _s = tt_probe(np.uint64(key), 0, TT_KEY, TT_MOVE, TT_SCORE, TT_DEPTH, TT_GEN)
    return int(move) if hit else 0


def warmup() -> bool:
    """Compile the exact original Storm root signature before reporting ready."""
    global NUMBA_READY, WARMUP_S
    from board_nb import START_FEN, from_fen
    from movegen_nb import generate_legal

    began = time.perf_counter()
    NUMBA_READY = False
    pos = from_fen(START_FEN)
    _ = perft_pos(pos, 2)
    packed = generate_legal(pos)
    bb, mb, st = pack_pos(pos)
    root = np.array(packed, dtype=np.int32)
    hist = np.empty(MAX_PLY + 8, dtype=np.uint64)
    undos = np.zeros((MAX_PLY, 7), dtype=np.uint64)
    stacks = np.zeros((MAX_PLY, MAX_MOVES), dtype=np.int32)
    scratches = np.zeros((MAX_PLY, MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(2, dtype=np.int64)
    aborted = np.zeros(1, dtype=np.int32)
    nodes[0], nodes[1] = 1024, 1
    if not check_clock(nodes, 10**15, True, aborted) or not aborted[0]:
        raise RuntimeError("Native monotonic-clock warmup did not abort")
    nodes.fill(0)
    aborted.fill(0)
    # Finite depth-one start-position search; compilation has no live deadline.
    _ = root_search_nb(
        bb, mb, st, root, len(packed), 1, hist, 0, int(root[0]),
        -INF, INF, 0, 600, 10**15, undos, stacks, scratches,
        TT_KEY, TT_MOVE, TT_SCORE, TT_DEPTH, TT_GEN, TT_AGE,
        KILLERS, HISTORY, NET, NN_LAST_BB, NN_ACC, nodes, aborted,
    )
    if not root_search_nb.nopython_signatures or aborted[0]:
        raise RuntimeError("Native root search was not compiled during import")
    WARMUP_S = time.perf_counter() - began
    NUMBA_READY = True
    return NUMBA_READY
