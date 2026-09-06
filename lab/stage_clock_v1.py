"""Stage clock-v1 candidate from last-good: late floor + dynamic ID stops only."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "dist" / "last-good"

TIME_NB_BASE = '''"""Middlegame clock. Increment is credited after we return; do not spend it."""

from __future__ import annotations

PANIC_MS = 250
HARD_MARGIN_MS = 400
SOFT_RESERVE_MS = 1500
INCREMENT_MS = 500
MIN_ITER_MS = 200
MIN_HARD_MS = 50
PLY_CAP = 300


def _clamp(n: int, lo: int, hi: int) -> int:
    return lo if n < lo else hi if n > hi else n


def allocation(time_left_ms: int, game_ply: int) -> tuple[str, float, float]:
    """Return ('panic', 0, 0) or ('search', soft_ms, hard_ms)."""
    if time_left_ms < PANIC_MS:
        return "panic", 0.0, 0.0
    remaining_our = _clamp((PLY_CAP - game_ply + 1) // 2, {floor}, 40)
    soft = (time_left_ms - SOFT_RESERVE_MS) / remaining_our + 0.5 * INCREMENT_MS
    if soft < 1.0:
        soft = 1.0
    hard = min(time_left_ms - HARD_MARGIN_MS, 2.0 * soft)
    if hard < MIN_HARD_MS:
        return "panic", 0.0, 0.0
    return "search", float(soft), float(hard)
'''

TIME_NB_HELPERS = '''

def soft_budget(soft_ms: float, asp_failed: bool = False) -> float:
    return soft_ms * 1.15 if asp_failed else soft_ms


def early_stop_ok(
    elapsed_ms: float, soft_ms: float, depth: int, pv_stable: bool
) -> bool:
    return depth >= 4 and pv_stable and elapsed_ms >= soft_ms * 0.88
'''

CORE_IMPORT = "from time_nb import early_stop_ok, soft_budget\n"


def time_nb_text(*, floor: int, helpers: bool) -> str:
    text = TIME_NB_BASE.format(floor=floor)
    if helpers:
        text += TIME_NB_HELPERS
    return text

SEARCH_ROOT_OLD = """    prev = 0
    last_nps = 700_000.0
    adj = 1 if adjudicate else 0
    nroot = len(packed_root)

    for depth in range(1, MAX_DEPTH + 1):
        now = time.perf_counter()
        elapsed_ms = (now - start) * 1000.0
        remaining_ms = hard_ms - elapsed_ms
        if depth > 1 and remaining_ms < 200.0:
            break
        if depth > 1 and elapsed_ms >= soft_ms:
            break
"""

SEARCH_ROOT_NEW = """    prev = 0
    prev_move = 0
    pv_stable = False
    asp_failed = False
    last_nps = 700_000.0
    adj = 1 if adjudicate else 0
    nroot = len(packed_root)

    for depth in range(1, MAX_DEPTH + 1):
        now = time.perf_counter()
        elapsed_ms = (now - start) * 1000.0
        remaining_ms = hard_ms - elapsed_ms
        if depth > 1 and remaining_ms < 200.0:
            break
        if depth > 1 and early_stop_ok(elapsed_ms, soft_ms, depth, pv_stable):
            break
        if depth > 1 and elapsed_ms >= soft_budget(soft_ms, asp_failed):
            break
"""

ASPIRATION_OLD = """        move, score = root_search_nb(*args)
        if depth > 1 and not aborted[0] and (score <= a or score >= b):
"""

ASPIRATION_NEW = """        move, score = root_search_nb(*args)
        asp_failed = bool(
            depth > 1 and not aborted[0] and (score <= a or score >= b)
        )
        if asp_failed:
"""

TAIL_OLD = """        if aborted[0] and depth > 1:
            break
        best = int(move)
        prev = int(score)
"""

TAIL_NEW = """        if aborted[0] and depth > 1:
            break
        pv_stable = depth >= 3 and int(move) == prev_move
        prev_move = int(move)
        best = int(move)
        prev = int(score)
"""

SEARCH_IMPORT_ANCHOR = "from tt_nb import EXACT, LOWER, UPPER, tt\n"
SEARCH_IMPORT_NEW = "from tt_nb import EXACT, LOWER, UPPER, tt\nfrom time_nb import early_stop_ok, soft_budget\n"

ID_OLD = """    prev = 0
    hist_base = list(game_zkeys[:-1] if game_zkeys else [])

    for depth in range(1, MAX_DEPTH + 1):
        now = time.perf_counter()
        elapsed_ms = (now - start) * 1000.0
        remaining_ms = hard_ms - elapsed_ms
        if depth > 1 and remaining_ms < 200:
            break
        if depth > 1 and elapsed_ms >= soft_ms:
            break
        _allow_abort = False
        window = (-INF, INF) if depth <= 1 else (prev - ASPIRATION, prev + ASPIRATION)
        try:
            move, score = _root_search(
                pos, packed_root, depth, hist_base, best, window[0], window[1]
            )
            if depth > 1 and (score <= window[0] or score >= window[1]):
                move, score = _root_search(pos, packed_root, depth, hist_base, best, -INF, INF)
            best = move
            prev = score
"""

ID_NEW = """    prev = 0
    prev_move = 0
    pv_stable = False
    asp_failed = False
    hist_base = list(game_zkeys[:-1] if game_zkeys else [])

    for depth in range(1, MAX_DEPTH + 1):
        now = time.perf_counter()
        elapsed_ms = (now - start) * 1000.0
        remaining_ms = hard_ms - elapsed_ms
        if depth > 1 and remaining_ms < 200:
            break
        if depth > 1 and early_stop_ok(elapsed_ms, soft_ms, depth, pv_stable):
            break
        if depth > 1 and elapsed_ms >= soft_budget(soft_ms, asp_failed):
            break
        _allow_abort = False
        window = (-INF, INF) if depth <= 1 else (prev - ASPIRATION, prev + ASPIRATION)
        try:
            move, score = _root_search(
                pos, packed_root, depth, hist_base, best, window[0], window[1]
            )
            asp_failed = depth > 1 and (score <= window[0] or score >= window[1])
            if asp_failed:
                move, score = _root_search(pos, packed_root, depth, hist_base, best, -INF, INF)
            pv_stable = depth >= 3 and move == prev_move
            prev_move = move
            best = move
            prev = score
"""


def patch_core(text: str, *, dynamic_id: bool) -> str:
    if dynamic_id:
        if CORE_IMPORT.strip() in text:
            raise SystemExit("core_nb already has clock-v1 import")
        needle = "from eval_nb import EG_TABLE, MG_TABLE\n"
        if needle not in text:
            raise SystemExit("core_nb import anchor missing")
        text = text.replace(needle, needle + CORE_IMPORT, 1)
        if SEARCH_ROOT_OLD not in text:
            raise SystemExit("core_nb search_root anchor missing")
        text = text.replace(SEARCH_ROOT_OLD, SEARCH_ROOT_NEW, 1)
        text = text.replace(ASPIRATION_OLD, ASPIRATION_NEW, 1)
        text = text.replace(TAIL_OLD, TAIL_NEW, 1)
    if "EVAL_STACK" in text:
        raise SystemExit("refusing clock-v1 stew: EVAL_STACK present in core_nb")
    return text


def patch_search(text: str, *, dynamic_id: bool) -> str:
    if not dynamic_id:
        return text
    if "from time_nb import early_stop_ok" in text:
        raise SystemExit("search_nb already patched")
    if SEARCH_IMPORT_ANCHOR not in text:
        raise SystemExit("search_nb import anchor missing")
    text = text.replace(SEARCH_IMPORT_ANCHOR, SEARCH_IMPORT_NEW, 1)
    if ID_OLD not in text:
        raise SystemExit("search_nb ID anchor missing")
    text = text.replace(ID_OLD, ID_NEW, 1)
    return text


def stage(dst: Path, *, variant: str) -> None:
    if variant == "full":
        floor, dynamic_id = 1, True
    elif variant == "floor":
        floor, dynamic_id = 1, False
    elif variant == "id":
        floor, dynamic_id = 20, True
    else:
        raise SystemExit(f"unknown variant {variant!r}; use full|floor|id")
    if not SRC.is_dir():
        raise SystemExit(f"missing source tree: {SRC}")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SRC, dst)
    (dst / "time_nb.py").write_text(
        time_nb_text(floor=floor, helpers=dynamic_id), encoding="utf-8"
    )
    core = patch_core((dst / "core_nb.py").read_text(encoding="utf-8"), dynamic_id=dynamic_id)
    (dst / "core_nb.py").write_text(core, encoding="utf-8")
    search = patch_search((dst / "search_nb.py").read_text(encoding="utf-8"), dynamic_id=dynamic_id)
    (dst / "search_nb.py").write_text(search, encoding="utf-8")
    print(f"clock-{variant} staged at {dst}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Stage clock brick from last-good.")
    parser.add_argument("dst", nargs="?", type=Path, default=ROOT / "dist" / "clock-v1")
    parser.add_argument("--variant", choices=("full", "floor", "id"), default="floor")
    args = parser.parse_args()
    stage(args.dst, variant=args.variant)


if __name__ == "__main__":
    main()
