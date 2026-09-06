#!/usr/bin/env python3
"""Signer: stage early24 from last-good, contest-TC 8 then 40. Does not promote."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/botuser/chess-tk")
VENV = ROOT / ".venv" / "bin" / "python"
CAND = Path("/home/botuser/chess-candidates/clock_cap")
TREE = CAND / "early24"
LAST_GOOD_ZIP = ROOT / "dist" / "last-good.zip"
LOG = ROOT / "lab" / "logs"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(line: str) -> None:
    LOG.mkdir(parents=True, exist_ok=True)
    with (LOG / "early24_tc.out").open("a", encoding="utf-8") as f:
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
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": f"{TREE}:{ROOT}"},
        capture_output=True,
        text=True,
        timeout=70,
        check=False,
    )
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()[-400:]
    log(f"warmup exit={r.returncode} {out}")
    if err:
        log(f"warmup err={err}")
    return r.returncode == 0 and "NUMBA_READY=True" in out


def gauntlet(games: int, log_name: str) -> int:
    return run(
        [
            str(VENV),
            "-m",
            "lab.gauntlet",
            "--agent",
            str(TREE),
            "--opponent",
            "baselines/greedy",
            "--games",
            str(games),
            "--base-ms",
            "120000",
            "--increment-ms",
            "500",
            "--stop-on-fail",
            "--log",
            str(LOG / log_name),
        ]
    )


def main() -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    started = time.monotonic()
    log(f"=== early24 contest-TC start {utc()} ===")
    log("parent=dist/last-good.zip  brick=early24  no promote")
    if not LAST_GOOD_ZIP.is_file():
        log(f"missing {LAST_GOOD_ZIP}")
        return 2
    rc = run(
        [
            str(VENV),
            str(ROOT / "lab" / "stage_clock_cap.py"),
            "--parent",
            str(LAST_GOOD_ZIP),
            "--out",
            str(CAND),
            "--only",
            "early24",
        ]
    )
    if rc != 0:
        log(f"stage failed exit={rc}")
        return rc
    text = (TREE / "time_nb.py").read_text(encoding="utf-8")
    if "cap = 24 if game_ply < 80 else 40" not in text:
        log("staged time_nb missing early24 cap")
        return 3
    if "early_stop_ok" in text or "soft_budget" in text:
        log("refusing stew time_nb")
        return 3
    if not warmup():
        log("NUMBA_READY False — abort (would be Python vs greedy, not a clock measurement)")
        return 4
    log("=== 8-game contest-TC gate ===")
    gate = gauntlet(8, "early24-tc8.jsonl")
    log(f"GATE_EXIT={gate}")
    if gate != 0:
        log("8-game gate failed — skip 40. last-good stays the zip.")
        return gate
    log("=== 40-game contest-TC soak ===")
    soak = gauntlet(40, "early24-tc40.jsonl")
    log(f"SOAK_EXIT={soak}")
    hours = (time.monotonic() - started) / 3600.0
    log(f"=== early24 contest-TC end {utc()} wall={hours:.2f}h ===")
    log("DO NOT PROMOTE. Human reads early24-tc8.jsonl / early24-tc40.jsonl.")
    return soak


if __name__ == "__main__":
    raise SystemExit(main())
