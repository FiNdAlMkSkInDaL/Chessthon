"""Packed 64 MB TT. 2^22 x 16 B. Ply-adjusted mates. No numpy, no torch."""

from __future__ import annotations

import struct

TT_BITS = 22
TT_SIZE = 1 << TT_BITS
TT_MASK = TT_SIZE - 1
ENTRY = 16  # Q key, I move, h score, B depth, B age|flag
_PACK = struct.Struct("<QIhBB")

EXACT, LOWER, UPPER = 0, 1, 2
MATE_WIN = 31_000
_FLAG_MASK = 3


def _to_tt(score: int, ply: int) -> int:
    if score >= MATE_WIN:
        return score + ply
    if score <= -MATE_WIN:
        return score - ply
    return score


def _from_tt(score: int, ply: int) -> int:
    if score >= MATE_WIN:
        return score - ply
    if score <= -MATE_WIN:
        return score + ply
    return score


class TT:
    __slots__ = ("data", "age")

    def __init__(self) -> None:
        self.data = bytearray(TT_SIZE * ENTRY)
        self.age = 1

    def new_search(self) -> None:
        self.age = (self.age + 1) & 63 or 1

    def clear(self) -> None:
        self.data[:] = b"\x00" * len(self.data)

    def probe(self, key: int) -> tuple[int, int, int, int] | None:
        """(move, depth, flag, raw_score) or None. Caller ply-adjusts via score_at."""
        idx = (key & TT_MASK) * ENTRY
        k, move, score, depth, gen = _PACK.unpack_from(self.data, idx)
        if k != key or k == 0:
            return None
        return move, depth, gen & _FLAG_MASK, score

    def score_at(self, raw: int, ply: int) -> int:
        return _from_tt(raw, ply)

    def store(self, key: int, move: int, depth: int, flag: int, score: int, ply: int) -> None:
        if key == 0:
            return
        idx = (key & TT_MASK) * ENTRY
        k, old_move, _old_s, old_depth, gen = _PACK.unpack_from(self.data, idx)
        if k == key and (gen >> 2) == self.age and old_depth > depth:
            return
        if k == key and not move:
            move = old_move
        packed = _to_tt(score, ply)
        if packed > 32767:
            packed = 32767
        elif packed < -32768:
            packed = -32768
        if depth > 255:
            depth = 255
        _PACK.pack_into(
            self.data,
            idx,
            key,
            move & 0xFFFFFFFF,
            packed,
            depth,
            (self.age << 2) | (flag & _FLAG_MASK),
        )


tt = TT()
