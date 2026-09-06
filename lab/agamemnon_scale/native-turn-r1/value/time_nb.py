"""Middlegame clock. Increment is credited after we return; do not spend it."""

from __future__ import annotations

PANIC_MS = 250
HARD_MARGIN_MS = 400
SOFT_RESERVE_MS = 1500
INCREMENT_MS = 500
MIN_ITER_MS = 200
MIN_HARD_MS = 50
PLY_CAP = 600


def _clamp(n: int, lo: int, hi: int) -> int:
    return lo if n < lo else hi if n > hi else n


def allocation(time_left_ms: int, game_ply: int) -> tuple[str, float, float]:
    """Return ('panic', 0, 0) or ('search', soft_ms, hard_ms)."""
    if time_left_ms < PANIC_MS:
        return "panic", 0.0, 0.0
    remaining_our = _clamp((PLY_CAP - game_ply + 1) // 2, 1, 40)
    soft = (time_left_ms - SOFT_RESERVE_MS) / remaining_our + 0.5 * INCREMENT_MS
    if soft < 1.0:
        soft = 1.0
    hard = min(time_left_ms - HARD_MARGIN_MS, 2.0 * soft)
    if hard < MIN_HARD_MS:
        return "panic", 0.0, 0.0
    return "search", float(soft), float(hard)
