"""Precomputed leapers, ray directions, zobrist. Magics are out of the freeze zip."""

from __future__ import annotations

import random

WHITE, BLACK = 0, 1

WP, WN, WB, WR, WQ, WK = 0, 1, 2, 3, 4, 5
BP, BN, BB, BR, BQ, BK = 6, 7, 8, 9, 10, 11
N_PIECES = 12

PIECE_CHAR = "PNBRQKpnbrqk"
CHAR_TO_PIECE = {c: i for i, c in enumerate(PIECE_CHAR)}

A1, B1, C1, D1, E1, F1, G1, H1 = range(8)
A8, B8, C8, D8, E8, F8, G8, H8 = range(56, 64)

WK_CASTLE, WQ_CASTLE, BK_CASTLE, BQ_CASTLE = 1, 2, 4, 8
CASTLE_ALL = 15
EP_NONE = 64
MASK64 = 0xFFFFFFFFFFFFFFFF

# Packed move: from 0-5, to 6-11, promo 12-14 (0 none, 1N 2B 3R 4Q),
# capture 15, ep 16, castle 17, double 18.
PROMO_NONE, PROMO_N, PROMO_B, PROMO_R, PROMO_Q = 0, 1, 2, 3, 4
PROMO_UCI = {1: "n", 2: "b", 3: "r", 4: "q"}
UCI_PROMO = {"n": 1, "b": 2, "r": 3, "q": 4}


def sq_file(sq: int) -> int:
    return sq & 7


def sq_rank(sq: int) -> int:
    return sq >> 3


def square(file: int, rank: int) -> int:
    return rank * 8 + file


def square_name(sq: int) -> str:
    return chr(ord("a") + (sq & 7)) + str((sq >> 3) + 1)


def parse_square(name: str) -> int:
    return (int(name[1]) - 1) * 8 + (ord(name[0]) - ord("a"))


def lsb(bb: int) -> int:
    return (bb & -bb).bit_length() - 1


def iter_bits(bb: int):
    while bb:
        bit = bb & -bb
        yield bit.bit_length() - 1
        bb ^= bit


def _build_leapers() -> tuple[list[int], list[int], list[list[int]]]:
    knight = [0] * 64
    king = [0] * 64
    pawn = [[0] * 64, [0] * 64]
    knight_d = ((1, 2), (1, -2), (-1, 2), (-1, -2), (2, 1), (2, -1), (-2, 1), (-2, -1))
    king_d = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    for sq in range(64):
        f, r = sq_file(sq), sq_rank(sq)
        for df, dr in knight_d:
            nsq = square(f + df, r + dr) if 0 <= f + df < 8 and 0 <= r + dr < 8 else -1
            if nsq >= 0:
                knight[sq] |= 1 << nsq
        for df, dr in king_d:
            nf, nr = f + df, r + dr
            if 0 <= nf < 8 and 0 <= nr < 8:
                king[sq] |= 1 << square(nf, nr)
        if r < 7:
            if f > 0:
                pawn[WHITE][sq] |= 1 << square(f - 1, r + 1)
            if f < 7:
                pawn[WHITE][sq] |= 1 << square(f + 1, r + 1)
        if r > 0:
            if f > 0:
                pawn[BLACK][sq] |= 1 << square(f - 1, r - 1)
            if f < 7:
                pawn[BLACK][sq] |= 1 << square(f + 1, r - 1)
    return knight, king, pawn


KNIGHT_ATK, KING_ATK, PAWN_ATK = _build_leapers()

# (df, dr) ??? file, rank. N, S, E, W, NE, NW, SE, SW.
RAY_DIRS = ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1))
ROOK_DIR_I = (0, 1, 2, 3)
BISHOP_DIR_I = (4, 5, 6, 7)

CASTLE_MASK = [CASTLE_ALL] * 64
CASTLE_MASK[A1] = CASTLE_ALL ^ WQ_CASTLE
CASTLE_MASK[H1] = CASTLE_ALL ^ WK_CASTLE
CASTLE_MASK[E1] = CASTLE_ALL ^ (WK_CASTLE | WQ_CASTLE)
CASTLE_MASK[A8] = CASTLE_ALL ^ BQ_CASTLE
CASTLE_MASK[H8] = CASTLE_ALL ^ BK_CASTLE
CASTLE_MASK[E8] = CASTLE_ALL ^ (BK_CASTLE | BQ_CASTLE)


def _build_zobrist() -> tuple[list[list[int]], int, list[int], list[int]]:
    rng = random.Random(0xC0FFEE)
    piece = [[rng.getrandbits(64) for _ in range(64)] for _ in range(N_PIECES)]
    side = rng.getrandbits(64)
    castle = [rng.getrandbits(64) for _ in range(16)]
    ep = [rng.getrandbits(64) for _ in range(8)]
    return piece, side, castle, ep


Z_PIECE, Z_SIDE, Z_CASTLE, Z_EP = _build_zobrist()
