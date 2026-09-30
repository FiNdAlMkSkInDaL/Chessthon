"""Stage qsearch quiet-checks from last-good. One variable. No HEAD stew."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ZIP = ROOT / "dist" / "agent.zip"

GEN_NOISY_TAIL = """        unmake_nb(bb, mb, st, mv, undo)
    return n


@njit(cache=False)
def pesto_nb(bb, st, tempo):
"""

GEN_NOISY_WITH_CHECKS = """        unmake_nb(bb, mb, st, mv, undo)
    return n


@njit(cache=False)
def gen_quiet_checks(bb, mb, st, out, scratch, start):
    undo = np.zeros(7, dtype=np.uint64)
    nps = gen_pseudo(bb, mb, st, scratch)
    us = np.int32(st[SIDE])
    them = us ^ 1
    n = start
    for i in range(nps):
        if n >= MAX_MOVES:
            break
        mv = scratch[i]
        if m_cap(mv) or m_promo(mv):
            continue
        make_nb(bb, mb, st, mv, undo)
        if (not in_check_nb(bb, st, us)) and in_check_nb(bb, st, them):
            out[n] = mv
            n += 1
        unmake_nb(bb, mb, st, mv, undo)
    return n


@njit(cache=False)
def pesto_nb(bb, st, tempo):
"""

QS_NOISY = """        n = gen_noisy(bb, mb, st, moves_buf, scratch)
        best = stand
"""

QS_NOISY_CHECKS = """        n = gen_noisy(bb, mb, st, moves_buf, scratch)
        if ply < QS_CHECK_PLY:
            n = gen_quiet_checks(bb, mb, st, moves_buf, scratch, n)
        best = stand
"""

CORE_DELTA = "DELTA = 200\n"
CORE_DELTA_PLY = "DELTA = 200\nQS_CHECK_PLY = 2\n"

QS_PRUNE = """        if not checked:
            promo = m_promo(move)
            if promo and promo != 4:
                continue
            cap_v = SEE_V[victim_pt(mb, move)]
            if promo:
                cap_v += SEE_V[promo] - SEE_V[0]
            if stand + cap_v + DELTA < alpha:
                continue
            if move != hash_move and see_nb(bb, mb, st, move) < 0:
                continue
"""

QS_PRUNE_SKIP_QUIET = """        if not checked:
            promo = m_promo(move)
            quiet = (not m_cap(move)) and promo == 0
            if not quiet:
                if promo and promo != 4:
                    continue
                cap_v = SEE_V[victim_pt(mb, move)]
                if promo:
                    cap_v += SEE_V[promo] - SEE_V[0]
                if stand + cap_v + DELTA < alpha:
                    continue
                if move != hash_move and see_nb(bb, mb, st, move) < 0:
                    continue
"""

PY_NOISY_TAIL = '''        unmake(pos, move, undo)
    return legal


def legal_uci(pos: Position) -> set[str]:
'''

PY_NOISY_WITH_CHECKS = '''        unmake(pos, move, undo)
    return legal


def generate_quiet_checks(pos: Position) -> list[int]:
    """Legal non-capture non-promo moves that give check. Qsearch only."""
    legal: list[int] = []
    us = pos.side
    for move in generate_legal(pos):
        if move_is_capture(move) or move_promo(move):
            continue
        undo = make(pos, move)
        if in_check(pos, pos.side):
            legal.append(move)
        unmake(pos, move, undo)
    return legal


def legal_uci(pos: Position) -> set[str]:
'''

PY_QS_MOVES = """        moves = generate_noisy(pos)
        best = stand
"""

PY_QS_MOVES_CHECKS = """        moves = generate_noisy(pos)
        if ply < QS_CHECK_PLY:
            moves.extend(generate_quiet_checks(pos))
        best = stand
"""

PY_DELTA = "DELTA = 200\n"
PY_DELTA_PLY = "DELTA = 200\nQS_CHECK_PLY = 2\n"

PY_QS_PRUNE = """            if not checked:
                promo = move_promo(move)
                if promo and promo != 4:
                    continue
                cap_v = SEE_VAL[_victim_pt(pos, move)]
                if promo:
                    cap_v += SEE_VAL[promo] - SEE_VAL[0]
                if stand + cap_v + DELTA < alpha:
                    continue
                if move != hash_move and see(pos, move) < 0:
                    continue
"""

PY_QS_PRUNE_SKIP_QUIET = """            if not checked:
                promo = move_promo(move)
                quiet = (not move_is_capture(move)) and promo == 0
                if not quiet:
                    if promo and promo != 4:
                        continue
                    cap_v = SEE_VAL[_victim_pt(pos, move)]
                    if promo:
                        cap_v += SEE_VAL[promo] - SEE_VAL[0]
                    if stand + cap_v + DELTA < alpha:
                        continue
                    if move != hash_move and see(pos, move) < 0:
                        continue
"""

PY_IMPORT_OLD = """from movegen_nb import (
    bishop_attacks,
    generate_legal,
    generate_noisy,
    in_check,
    rook_attacks,
)
"""

PY_IMPORT_NEW = """from movegen_nb import (
    bishop_attacks,
    generate_legal,
    generate_noisy,
    generate_quiet_checks,
    in_check,
    rook_attacks,
)
"""


def parent_zip(explicit: Path | None = None) -> Path:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"parent zip missing: {path}")
        return path
    for path in (ARCHIVE_ZIP, ROOT / "dist" / "agent.zip", ROOT / "dist" / "last-good.zip"):
        if path.is_file():
            return path
    raise SystemExit("no submitted agent.zip / dist/last-good.zip")


def _refuse(core: str, time_nb: str) -> None:
    if "ENABLE_LMR = True" in core:
        raise SystemExit("refusing stew: ENABLE_LMR is True")
    if "early_stop_ok" in time_nb or "soft_budget" in time_nb:
        raise SystemExit("refusing stew: dynamic ID in time_nb")
    if "def gen_quiet_checks(" in core:
        raise SystemExit("quiet checks already present")


def patch_core(text: str) -> str:
    if CORE_DELTA not in text:
        raise SystemExit("core_nb DELTA anchor missing")
    if text.count(CORE_DELTA) != 1:
        raise SystemExit("core_nb DELTA not unique")
    text = text.replace(CORE_DELTA, CORE_DELTA_PLY, 1)
    if GEN_NOISY_TAIL not in text:
        raise SystemExit("core_nb gen_noisy tail missing")
    if text.count(GEN_NOISY_TAIL) != 1:
        raise SystemExit("core_nb gen_noisy tail not unique")
    text = text.replace(GEN_NOISY_TAIL, GEN_NOISY_WITH_CHECKS, 1)
    if QS_NOISY not in text:
        raise SystemExit("core_nb qsearch noisy anchor missing")
    if text.count(QS_NOISY) != 1:
        raise SystemExit("core_nb qsearch noisy anchor not unique")
    text = text.replace(QS_NOISY, QS_NOISY_CHECKS, 1)
    if QS_PRUNE not in text:
        raise SystemExit("core_nb qsearch prune anchor missing")
    if text.count(QS_PRUNE) != 1:
        raise SystemExit("core_nb qsearch prune anchor not unique")
    return text.replace(QS_PRUNE, QS_PRUNE_SKIP_QUIET, 1)


def patch_movegen(text: str) -> str:
    if PY_NOISY_TAIL not in text:
        raise SystemExit("movegen_nb generate_noisy tail missing")
    if text.count(PY_NOISY_TAIL) != 1:
        raise SystemExit("movegen_nb generate_noisy tail not unique")
    return text.replace(PY_NOISY_TAIL, PY_NOISY_WITH_CHECKS, 1)


def patch_search(text: str) -> str:
    if PY_DELTA not in text:
        raise SystemExit("search_nb DELTA missing")
    if text.count(PY_DELTA) != 1:
        raise SystemExit("search_nb DELTA not unique")
    text = text.replace(PY_DELTA, PY_DELTA_PLY, 1)
    if PY_IMPORT_OLD not in text:
        raise SystemExit("search_nb movegen import missing")
    text = text.replace(PY_IMPORT_OLD, PY_IMPORT_NEW, 1)
    if PY_QS_MOVES not in text:
        raise SystemExit("search_nb qsearch noisy anchor missing")
    if text.count(PY_QS_MOVES) != 1:
        raise SystemExit("search_nb qsearch noisy anchor not unique")
    text = text.replace(PY_QS_MOVES, PY_QS_MOVES_CHECKS, 1)
    if PY_QS_PRUNE not in text:
        raise SystemExit("search_nb qsearch prune anchor missing")
    if text.count(PY_QS_PRUNE) != 1:
        raise SystemExit("search_nb qsearch prune anchor not unique")
    return text.replace(PY_QS_PRUNE, PY_QS_PRUNE_SKIP_QUIET, 1)


def stage(dst: Path, *, zpath: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as archive:
        archive.extractall(dst)
    if not (dst / "agent.py").is_file():
        raise SystemExit(f"{zpath} has no agent.py at zip root")
    core = (dst / "core_nb.py").read_text(encoding="utf-8")
    time_nb = (dst / "time_nb.py").read_text(encoding="utf-8")
    _refuse(core, time_nb)
    (dst / "core_nb.py").write_text(patch_core(core), encoding="utf-8")
    mega = (dst / "movegen_nb.py").read_text(encoding="utf-8")
    (dst / "movegen_nb.py").write_text(patch_movegen(mega), encoding="utf-8")
    search = (dst / "search_nb.py").read_text(encoding="utf-8")
    (dst / "search_nb.py").write_text(patch_search(search), encoding="utf-8")
    print(f"qs-checks staged {zpath} -> {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage qsearch quiet-checks from last-good.")
    parser.add_argument("dst", type=Path, nargs="?", default=ROOT / "dist" / "qs-checks")
    parser.add_argument("--parent", type=Path, default=None)
    args = parser.parse_args()
    stage(args.dst, zpath=parent_zip(args.parent))


if __name__ == "__main__":
    main()
