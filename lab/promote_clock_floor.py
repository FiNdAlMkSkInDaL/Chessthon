#!/usr/bin/env python3
"""Promote clock-floor zip to last-good on the signer. Run from chess-tk venv."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path("/home/botuser/chess-tk")
CAND = Path("/home/botuser/chess-candidates/clock-floor")
DIST = ROOT / "dist"


def main() -> None:
    pack_src = Path("/tmp/clock-pack")
    if pack_src.exists():
        shutil.rmtree(pack_src)
    shutil.copytree(CAND, pack_src)
    import os
    import sys

    sys.path.insert(0, str(ROOT))
    os.chdir(pack_src)
    from harness.package import build

    out = DIST / "clock-floor.zip"
    build(pack_src, out, ("weights",))
    prev1 = DIST / "last-good.prev1.zip"
    prev2 = DIST / "last-good.prev2.zip"
    lg = DIST / "last-good.zip"
    if prev1.is_file():
        shutil.copy2(prev1, prev2)
    shutil.copy2(lg, prev1)
    shutil.copy2(out, lg)
    unpacked = DIST / "last-good"
    if unpacked.exists():
        shutil.rmtree(unpacked)
    unpacked.mkdir(parents=True)
    with zipfile.ZipFile(lg) as zf:
        zf.extractall(unpacked)
    cand_lg = Path("/home/botuser/chess-candidates/last-good")
    if cand_lg.exists():
        shutil.rmtree(cand_lg)
    shutil.copytree(CAND, cand_lg)
    print(f"promoted {out} -> {lg}")


if __name__ == "__main__":
    main()
