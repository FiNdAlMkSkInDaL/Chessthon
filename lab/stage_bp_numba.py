"""Stage bp-numba candidate from last-good: exclusive bishop-pair in pesto_nb (+ Python if missing)."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BP_CONST_OLD = "SEE_PRUNE_MAX_D = 6\n"
BP_CONST_NEW = "SEE_PRUNE_MAX_D = 6\nBP_MG = 25\nBP_EG = 40\n"

PESTO_OLD = """    score = (mg_w - mg_b) * phase + (eg_w - eg_b) * (24 - phase)
    score //= 24
"""

PESTO_NEW = """    mg_diff = mg_w - mg_b
    eg_diff = eg_w - eg_b
    wb = popc(bb[2])
    bbc = popc(bb[8])
    if wb >= 2 and bbc < 2:
        mg_diff += BP_MG
        eg_diff += BP_EG
    elif bbc >= 2 and wb < 2:
        mg_diff -= BP_MG
        eg_diff -= BP_EG
    score = mg_diff * phase + eg_diff * (24 - phase)
    score //= 24
"""

EVAL_TEMPO = "TEMPO = 10\n"
EVAL_TEMPO_BP = "TEMPO = 10\nBP_MG = 25\nBP_EG = 40\n"

EVAL_OLD = """    mg_score = mg_w - mg_b
    eg_score = eg_w - eg_b
    score = (mg_score * phase + eg_score * (24 - phase)) // 24
"""

EVAL_NEW = """    mg_score = mg_w - mg_b
    eg_score = eg_w - eg_b
    wb = pos.bb[2].bit_count()
    bbc = pos.bb[8].bit_count()
    if wb >= 2 and bbc < 2:
        mg_score += BP_MG
        eg_score += BP_EG
    elif bbc >= 2 and wb < 2:
        mg_score -= BP_MG
        eg_score -= BP_EG
    score = (mg_score * phase + eg_score * (24 - phase)) // 24
"""


def _src(explicit: Path | None) -> Path:
    src = explicit or (ROOT / "dist" / "last-good")
    if not src.is_dir():
        raise SystemExit(f"missing source tree: {src}")
    return src


def patch_core(text: str) -> str:
    if "ENABLE_LMR = True" in text:
        raise SystemExit("refusing bp-numba stew: ENABLE_LMR is True")
    if "from time_nb import early_stop_ok" in text or "soft_budget(" in text:
        raise SystemExit("refusing bp-numba stew: dynamic ID present in core_nb")
    if "BP_MG" in text:
        raise SystemExit("refusing bp-numba stew: BP_MG already present")
    if BP_CONST_OLD not in text:
        raise SystemExit("core_nb SEE_PRUNE_MAX_D anchor missing")
    text = text.replace(BP_CONST_OLD, BP_CONST_NEW, 1)
    if PESTO_OLD not in text:
        raise SystemExit("core_nb pesto_nb taper anchor missing")
    text = text.replace(PESTO_OLD, PESTO_NEW, 1)
    return text


def patch_eval(text: str) -> str:
    if "BP_MG" in text and "wb >= 2" in text:
        return text
    if EVAL_TEMPO not in text:
        raise SystemExit("eval_nb TEMPO anchor missing")
    if "BP_MG" not in text:
        text = text.replace(EVAL_TEMPO, EVAL_TEMPO_BP, 1)
    if EVAL_OLD in text:
        text = text.replace(EVAL_OLD, EVAL_NEW, 1)
    return text


def stage(dst: Path, *, src: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    core = patch_core((dst / "core_nb.py").read_text(encoding="utf-8"))
    (dst / "core_nb.py").write_text(core, encoding="utf-8")
    eval_path = dst / "eval_nb.py"
    eval_path.write_text(patch_eval(eval_path.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"bp-numba staged at {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage bishop-pair Numba brick from last-good.")
    parser.add_argument("dst", nargs="?", type=Path, default=ROOT / "dist" / "bp-numba")
    parser.add_argument("--src", type=Path, default=None)
    args = parser.parse_args()
    stage(args.dst, src=_src(args.src))


if __name__ == "__main__":
    main()
