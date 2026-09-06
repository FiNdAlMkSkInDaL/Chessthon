"""Stage a one-line core_nb constant change from last-good. Measurement parent only."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src(explicit: Path | None) -> Path:
    src = explicit or (ROOT / "dist" / "last-good")
    if not (src / "core_nb.py").is_file():
        raise SystemExit(f"missing source tree: {src}")
    return src


def _refuse_stew(text: str) -> None:
    if "ENABLE_LMR = True" in text:
        raise SystemExit("refusing const stew: ENABLE_LMR is True")
    if "from time_nb import early_stop_ok" in text or "soft_budget(" in text:
        raise SystemExit("refusing const stew: dynamic ID present in core_nb")


def stage(dst: Path, *, src: Path, old: str, new: str) -> None:
    if old == new:
        raise SystemExit("old and new are identical")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    core_path = dst / "core_nb.py"
    text = core_path.read_text(encoding="utf-8")
    _refuse_stew(text)
    if old not in text:
        raise SystemExit(f"anchor missing in core_nb: {old!r}")
    if text.count(old) != 1:
        raise SystemExit(f"anchor not unique ({text.count(old)}): {old!r}")
    core_path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"const staged at {dst}: {old!r} -> {new!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage a unique core_nb string swap from last-good.")
    parser.add_argument("dst", type=Path)
    parser.add_argument("--src", type=Path, default=None)
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    args = parser.parse_args()
    stage(args.dst, src=_src(args.src), old=args.old, new=args.new)


if __name__ == "__main__":
    main()
