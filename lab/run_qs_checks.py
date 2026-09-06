#!/usr/bin/env python3
"""Signer: stage qs-checks from last-good, soak, screen vs path last-good. No promote."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/botuser/chess-tk")
VENV = ROOT / ".venv" / "bin" / "python"
CAND = Path("/home/botuser/chess-candidates/qs-checks")
LAST_GOOD = ROOT / "dist" / "last-good"
LAST_GOOD_ZIP = ROOT / "dist" / "last-good.zip"
LOG = ROOT / "lab" / "logs"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(line: str) -> None:
    LOG.mkdir(parents=True, exist_ok=True)
    with (LOG / "qs_checks.out").open("a", encoding="utf-8") as f:
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
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()[-400:]
    log(f"warmup exit={r.returncode} {out}")
    if err:
        log(f"warmup err={err}")
    return r.returncode == 0 and "NUMBA_READY=True" in out


def gauntlet(agent: Path, opponent: str, games: int, log_name: str, *, base_ms: int, inc_ms: int) -> int:
    return run(
        [
            str(VENV),
            "-m",
            "lab.gauntlet",
            "--agent",
            str(agent),
            "--opponent",
            opponent,
            "--games",
            str(games),
            "--base-ms",
            str(base_ms),
            "--increment-ms",
            str(inc_ms),
            "--stop-on-fail",
            "--log",
            str(LOG / log_name),
        ]
    )


def main() -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    started = time.monotonic()
    log(f"=== qs-checks start {utc()} ===")
    log("parent=dist/last-good.zip  brick=quiet-checks-in-qsearch  no promote")
    if not LAST_GOOD_ZIP.is_file():
        log(f"missing {LAST_GOOD_ZIP}")
        return 2
    rc = run(
        [
            str(VENV),
            str(ROOT / "lab" / "stage_qs_checks.py"),
            str(CAND),
            "--parent",
            str(LAST_GOOD_ZIP),
        ]
    )
    if rc != 0:
        log(f"stage failed exit={rc}")
        return rc
    if "def gen_quiet_checks(" not in (CAND / "core_nb.py").read_text(encoding="utf-8"):
        log("staged core_nb missing gen_quiet_checks")
        return 3
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    t = run([str(VENV), "-m", "lab.test_qs_checks"], cwd=CAND, env=env)
    log(f"test_qs_checks exit={t}")
    if t != 0:
        return t
    if not warmup():
        log("NUMBA_READY False — abort")
        return 4
    # Sanity: Numba root must play the quiet back-rank mate, not a stand-pat shuffle.
    probe = subprocess.run(
        [
            str(VENV),
            "-c",
            "from agent import get_move; "
            "m=get_move('6k1/5ppp/8/8/4r3/8/5PPP/6K1 b - - 0 1', 5000); "
            "print(m); raise SystemExit(0 if m=='e4e1' else 1)",
        ],
        cwd=CAND,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=70,
        check=False,
    )
    log(f"numba Re1# probe exit={probe.returncode} out={(probe.stdout or '').strip()} err={(probe.stderr or '')[-300:]}")
    if probe.returncode != 0:
        return 6
    log("=== 40-game soak vs greedy 3s+50 ===")
    soak = gauntlet(CAND, "baselines/greedy", 40, "qs-checks-soak.jsonl", base_ms=3000, inc_ms=50)
    log(f"SOAK_EXIT={soak}")
    if soak != 0:
        log("soak failed — do not screen, do not pack")
        return soak
    if not (LAST_GOOD / "agent.py").is_file():
        log("missing dist/last-good tree")
        return 5
    log("=== 120-game screen vs path last-good 3s+50 ===")
    screen = gauntlet(
        CAND, str(LAST_GOOD), 120, "qs-checks-screen.jsonl", base_ms=3000, inc_ms=50
    )
    log(f"SCREEN_EXIT={screen}")
    run([str(VENV), "-m", "lab.screen", str(LOG / "qs-checks-screen.jsonl"), "--min-games", "120"])
    hours = (time.monotonic() - started) / 3600.0
    log(f"=== qs-checks end {utc()} wall={hours:.2f}h ===")
    log("DO NOT PROMOTE from this process. KEEP + soak 0-fail then pack by hand.")
    return 0 if screen == 0 else screen


if __name__ == "__main__":
    raise SystemExit(main())
