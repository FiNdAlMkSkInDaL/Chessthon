"""Signer-only exact-ZIP smoke using the untouched starter runner protocol."""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

import chess


ROOT = Path(os.environ.get("RELEASE_PROBE_ROOT", "/agent")).resolve()
COLD_IMPORT_TARGET_S = float(os.environ.get("COLD_IMPORT_TARGET_S", "55"))
COLD_IMPORT_LIMIT_S = float(os.environ.get("COLD_IMPORT_LIMIT_S", "60"))
MOVE_PROBE_LIMIT_S = float(os.environ.get("MOVE_PROBE_LIMIT_S", "0.55"))
HOT_PATH_WALL_LIMIT_S = float(os.environ.get("HOT_PATH_WALL_LIMIT_S", "70"))

FENS = (
    chess.STARTING_FEN,
    "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",  # castling available
    "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3",  # EP available
    "8/5P1k/8/8/8/8/8/4K3 w - - 0 1",  # promotion generation
)


class ProbeError(RuntimeError):
    pass


def _read_line(process: subprocess.Popen[bytes], deadline: float) -> bytes:
    if process.stdout is None:
        raise ProbeError("runner has no protocol stdout")
    data = bytearray()
    fd = process.stdout.fileno()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeError("protocol deadline elapsed")
        readable, _, _ = select.select([fd], [], [], remaining)
        if not readable:
            raise ProbeError("protocol deadline elapsed")
        chunk = os.read(fd, 4096)
        if not chunk:
            raise ProbeError(f"runner exited ({process.poll()})")
        data.extend(chunk)
        if b"\n" in data:
            line, _, _ = data.partition(b"\n")
            return bytes(line)
        if len(data) > 4096:
            raise ProbeError("runner exceeded the protocol output cap")


def _json_line(process: subprocess.Popen[bytes], deadline: float) -> dict[str, object]:
    raw = _read_line(process, deadline)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"malformed protocol response: {raw!r}") from exc
    if not isinstance(value, dict):
        raise ProbeError(f"protocol response is not an object: {value!r}")
    return value


def _run_hot_path() -> None:
    env = dict(os.environ)
    env["HOT_PATH_REQUIRE"] = "1"
    env.pop("HOT_PATH_ALLOW_SLOW", None)
    env["NUMBA_CACHE_DIR"] = "/tmp/hot-numba-cache"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "lab.test_hot_path"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=HOT_PATH_WALL_LIMIT_S,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("Numba hot-path gate timed out") from exc
    print(result.stdout, end="")
    if result.returncode:
        raise ProbeError(f"Numba hot-path gate failed ({result.returncode})")


def _run_runner_smoke() -> None:
    if not 0 < COLD_IMPORT_TARGET_S <= COLD_IMPORT_LIMIT_S:
        raise ProbeError("invalid cold-import target/limit")
    env = dict(os.environ)
    env["NUMBA_CACHE_DIR"] = "/tmp/cold-numba-cache"
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "runner.py"), str(ROOT)],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        env=env,
    )
    try:
        started = time.monotonic()
        ready = _json_line(process, started + COLD_IMPORT_LIMIT_S)
        elapsed = time.monotonic() - started
        if ready.get("ready") is not True:
            raise ProbeError(f"runner did not send ready: {ready!r}")
        print(f"COLD RUNNER READY {elapsed:.2f}s")
        if elapsed > COLD_IMPORT_TARGET_S:
            raise ProbeError(
                f"cold runner {elapsed:.2f}s exceeds conservative "
                f"{COLD_IMPORT_TARGET_S:.0f}s target"
            )
        if process.stdin is None:
            raise ProbeError("runner has no protocol stdin")
        for fen in FENS:
            board = chess.Board(fen)
            legal = {move.uci() for move in board.legal_moves}
            process.stdin.write(
                (json.dumps({"fen": fen, "time_left_ms": 100}) + "\n").encode()
            )
            process.stdin.flush()
            response = _json_line(process, time.monotonic() + MOVE_PROBE_LIMIT_S)
            move = response.get("move")
            if not isinstance(move, str) or move not in legal:
                raise ProbeError(f"illegal root result {move!r} for {fen}")
            print(f"ROOT LEGAL {move} {fen}")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


def main() -> None:
    _run_hot_path()
    _run_runner_smoke()
    print("EXACT-ZIP RUNNER SMOKE OK")


if __name__ == "__main__":
    try:
        main()
    except ProbeError as exc:
        raise SystemExit(f"RELEASE PROBE FAILED: {exc}") from exc
