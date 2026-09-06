"""Stage improving candidate from last-good: EVAL_STACK gates RFP and NMP only."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src(explicit: Path | None) -> Path:
    src = explicit or (ROOT / "dist" / "last-good")
    if not src.is_dir():
        raise SystemExit(f"missing source tree: {src}")
    return src

EVAL_STACK_DECL = "EVAL_STACK = np.zeros(MAX_PLY, dtype=np.int32)\n"
HISTORY_DECL = "HISTORY = np.zeros((12, 64), dtype=np.int32)\n"

KILLERS_FILL = "    KILLERS.fill(0)\n"
KILLERS_PLUS_STACK = "    KILLERS.fill(0)\n    EVAL_STACK.fill(0)\n"

STATIC_OLD = """    static_eval = 0
    if not checked:
        static_eval = evaluate_nb(bb, st, adjudicate)
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
            and has_nm_pieces(bb, np.int32(st[SIDE]))
        ):
"""

STATIC_NEW = """    static_eval = 0
    if not checked:
        static_eval = evaluate_nb(bb, st, adjudicate)
        EVAL_STACK[ply] = static_eval
        improving = ply < 2 or static_eval >= EVAL_STACK[ply - 2]
        if (
            (not is_pv)
            and (not adjudicate)
            and depth <= RFP_MAX_D
            and beta > -MATE_WIN
            and beta < MATE_WIN
            and static_eval >= beta + RFP_MARGIN * depth
            and improving
        ):
            return static_eval
        if (
            (not is_pv)
            and (not adjudicate)
            and depth >= NMP_MIN_D
            and has_nm_pieces(bb, np.int32(st[SIDE]))
            and improving
        ):
"""


def _refuse_stew(text: str) -> None:
    if "ENABLE_LMR = True" in text:
        raise SystemExit("refusing improving stew: ENABLE_LMR is True")
    if "from time_nb import early_stop_ok" in text or "soft_budget(" in text:
        raise SystemExit("refusing improving stew: dynamic ID present in core_nb")
    if "BP_MG" in text:
        raise SystemExit("refusing improving stew: bishop-pair already in core_nb")
    if "EVAL_STACK" in text:
        raise SystemExit("refusing improving stew: EVAL_STACK already present")


def patch_core(text: str) -> str:
    _refuse_stew(text)
    if HISTORY_DECL not in text:
        raise SystemExit("core_nb HISTORY decl missing")
    text = text.replace(HISTORY_DECL, EVAL_STACK_DECL + HISTORY_DECL, 1)
    if KILLERS_FILL not in text:
        raise SystemExit("core_nb KILLERS.fill missing")
    text = text.replace(KILLERS_FILL, KILLERS_PLUS_STACK, 1)
    if STATIC_OLD not in text:
        raise SystemExit("core_nb RFP/NMP anchor missing — parent is not last-good")
    text = text.replace(STATIC_OLD, STATIC_NEW, 1)
    return text


def stage(dst: Path, *, src: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    core = patch_core((dst / "core_nb.py").read_text(encoding="utf-8"))
    (dst / "core_nb.py").write_text(core, encoding="utf-8")
    print(f"improving staged at {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage improving brick from last-good.")
    parser.add_argument("dst", nargs="?", type=Path, default=ROOT / "dist" / "improving")
    parser.add_argument("--src", type=Path, default=None, help="parent tree (default dist/last-good)")
    args = parser.parse_args()
    stage(args.dst, src=_src(args.src))


if __name__ == "__main__":
    main()
