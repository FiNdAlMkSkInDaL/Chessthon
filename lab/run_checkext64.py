#!/usr/bin/env python3
"""Signer: CHECK_EXT_PLY 48->64 from last-good. Soak then screen vs path last-good."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/botuser/chess-tk")
VENV = ROOT / ".venv" / "bin" / "python"
CAND = Path("/home/botuser/chess-candidates/checkext64")
LAST_GOOD = ROOT / "dist" / "last-good"
LOG = ROOT / "lab" / "logs"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(line: str) -> None:
    LOG.mkdir(parents=True, exist_ok=True)
    with (LOG / "checkext64.out").open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def run(args: list[str], *, cwd: Path = ROOT, env: dict | None = None) -> int:
    e = os.environ.copy()
    if env:
        e.update(env)
    log("$ " + " ".join(args))
    return subprocess.run(args, cwd=cwd, env=e, check=False).returncode


def warmup() -> bool:
    r = subprocess.run(
        [
            str(VENV),
            "-c",
            "import core_nb; ok=bool(core_nb.warmup()); "
            "print(f'NUMBA_READY={core_nb.NUMBA_READY} WARMUP_S={core_nb.WARMUP_S:.2f} ok={ok}')",
        ],
        cwd=CAND,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=70,
        check=False,
    )
    log(f"warmup exit={r.returncode} {(r.stdout or '').strip()}")
    if r.stderr:
        log(f"warmup err={(r.stderr or '')[-300:]}")
    return r.returncode == 0 and "NUMBA_READY=True" in (r.stdout or "")


def gauntlet(opp: str, games: int, log_name: str) -> int:
    return run(
        [
            str(VENV),
            "-m",
            "lab.gauntlet",
            "--agent",
            str(CAND),
            "--opponent",
            opp,
            "--games",
            str(games),
            "--base-ms",
            "3000",
            "--increment-ms",
            "50",
            "--stop-on-fail",
            "--log",
            str(LOG / log_name),
        ]
    )


def main() -> int:
    os.chdir(ROOT)
    log(f"=== checkext64 start {utc()} ===")
    rc = run(
        [
            str(VENV),
            str(ROOT / "lab" / "stage_const.py"),
            str(CAND),
            "--src",
            str(LAST_GOOD),
            "--old",
            "CHECK_EXT_PLY = 48",
            "--new",
            "CHECK_EXT_PLY = 64",
        ]
    )
    if rc != 0:
        log(f"stage failed {rc}")
        return rc
    if "CHECK_EXT_PLY = 64" not in (CAND / "core_nb.py").read_text(encoding="utf-8"):
        log("patch missing")
        return 3
    if not warmup():
        return 4
    soak = gauntlet("baselines/greedy", 40, "checkext64-soak.jsonl")
    log(f"SOAK_EXIT={soak}")
    if soak != 0:
        return soak
    screen = gauntlet(str(LAST_GOOD), 120, "checkext64-screen.jsonl")
    log(f"SCREEN_EXIT={screen}")
    run([str(VENV), "-m", "lab.screen", str(LOG / "checkext64-screen.jsonl"), "--min-games", "120"])
    log(f"=== checkext64 end {utc()} ===")
    return 0 if screen == 0 else screen


if __name__ == "__main__":
    raise SystemExit(main())
