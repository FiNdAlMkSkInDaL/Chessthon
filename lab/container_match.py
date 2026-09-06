"""Competition-shaped, two-container match between two exact submission ZIPs.

This is a lab evaluator, not a packager and not an uploader.  It audits and
cleanly extracts each exact ZIP, builds a SHA-tagged Linux/amd64 image, then
runs the untouched official runner in a separate constrained container for
each player.  Paired games reuse one held-out FEN while swapping both colour
and physical CPU assignment.

The published protocol, clock and resource envelope can be reproduced. This
uses only the pinned packages imported by these engines; the full private
platform image, tournament CPU and surrounding host cannot be made identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import chess

from harness.referee import FAILED_TERMINATIONS, play_match
from harness.rules import BASE_MS, INCREMENT_MS, INIT_BUDGET_S, PLY_CAP
from harness.sandbox import Agent
from lab.release_audit import audit


IMAGE_PREFIX = "chess-tk-match"
IMAGE_PLATFORM = "linux/amd64"
CONTAINER_MEMORY = "2g"
CONTAINER_TMPFS = "/tmp:rw,nosuid,nodev,size=256m,mode=1777"
MIN_HOST_MEMORY_BYTES = 5 * 1024**3
DEFAULT_PAIRS = 10
DEFAULT_OPENING_OFFSET = 100
REQUIRED_CONTROLLER_PYTHON = (3, 12)
REQUIRED_CHESS_VERSION = "1.11.2"
REQUIRED_NUMPY_VERSION = "2.5.2"
REQUIRED_NUMBA_VERSION = "0.67.0"
WARMUP_TARGET_S = 50.0
COLD_IMPORT_TARGET_S = 55.0
EXPECTED_MEMORY_BYTES = 2 * 1024**3
EXPECTED_TMP_BYTES = 256 * 1024**2
EXPECTED_PIDS = 128


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def controller_runtime(
    python_version: tuple[int, int] | None = None,
    chess_version: str | None = None,
) -> dict[str, Any]:
    """Validate the referee/controller runtime before a measured match."""
    version = sys.version_info[:2] if python_version is None else python_version
    installed_chess = chess.__version__ if chess_version is None else chess_version
    if tuple(version) != REQUIRED_CONTROLLER_PYTHON:
        raise SystemExit(
            "measured matches require controller Python 3.12; running "
            f"{version[0]}.{version[1]}"
        )
    if installed_chess != REQUIRED_CHESS_VERSION:
        raise SystemExit(
            f"measured matches require chess {REQUIRED_CHESS_VERSION}; running "
            f"{installed_chess}"
        )
    return {
        "python": platform.python_version(),
        "executable": sys.executable,
        "implementation": platform.python_implementation(),
        "chess": installed_chess,
    }


def source_provenance(root: Path) -> dict[str, Any]:
    starter_sha_path = root / "lab" / "STARTER_SHA"
    paths = {
        "harness/runner.py": root / "harness" / "runner.py",
        "harness/referee.py": root / "harness" / "referee.py",
        "harness/sandbox.py": root / "harness" / "sandbox.py",
        "harness/rules.py": root / "harness" / "rules.py",
        "lab/docker/MatchAgent.Dockerfile": root
        / "lab"
        / "docker"
        / "MatchAgent.Dockerfile",
        "lab/docker/match_image_probe.py": root
        / "lab"
        / "docker"
        / "match_image_probe.py",
        "lab/container_match.py": Path(__file__).resolve(),
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing or not starter_sha_path.is_file():
        names = missing + ([] if starter_sha_path.is_file() else ["lab/STARTER_SHA"])
        raise SystemExit("provenance input missing: " + ", ".join(names))
    return {
        "starter_commit": starter_sha_path.read_text(encoding="utf-8").strip(),
        "starter_sha_file_sha256": sha256_path(starter_sha_path),
        "files_sha256": {name: sha256_path(path) for name, path in paths.items()},
    }


def parse_cpu_pair(value: str) -> tuple[int, int]:
    try:
        parts = tuple(int(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("CPU pair must be two integers, e.g. 0,1") from exc
    if len(parts) != 2 or min(parts) < 0 or parts[0] == parts[1]:
        raise argparse.ArgumentTypeError("CPU pair must contain two distinct non-negative IDs")
    return parts[0], parts[1]


def load_openings(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise SystemExit(f"opening file not found: {path}")
    fens = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not fens:
        raise SystemExit(f"opening file contains no FENs: {path}")
    return fens


def validate_selected_fens(plans: Iterable["GamePlan"]) -> dict[str, Any]:
    selected: dict[int, str] = {}
    for plan in plans:
        selected[plan.opening_index] = plan.fen
    for index, fen in sorted(selected.items()):
        try:
            board = chess.Board(fen)
        except ValueError as exc:
            raise SystemExit(f"invalid selected FEN at opening index {index}: {exc}") from exc
        if not board.is_valid():
            raise SystemExit(f"invalid selected chess position at opening index {index}: {fen}")
        if board.outcome(claim_draw=True) is not None:
            raise SystemExit(f"terminal selected FEN at opening index {index}: {fen}")
    digest = hashlib.sha256()
    for index, fen in sorted(selected.items()):
        digest.update(f"{index}\0{fen}\n".encode("utf-8"))
    return {
        "count": len(selected),
        "indices": sorted(selected),
        "selection_sha256": digest.hexdigest(),
        "all_valid_nonterminal": True,
    }


@dataclass(frozen=True)
class ArchiveIdentity:
    source_path: Path
    snapshot_path: Path
    sha256: str
    zip_bytes: int
    uncompressed_bytes: int
    image_tag: str

    @property
    def path(self) -> Path:
        """Original user-facing path; builds always use snapshot_path."""
        return self.source_path


@dataclass(frozen=True)
class GamePlan:
    game: int
    pair: int
    opening_index: int
    fen: str
    white_role: str
    black_role: str
    white_cpu: int
    black_cpu: int


@dataclass
class TimedAgent:
    """Duck-typed harness Agent wrapper that records only orchestration timing."""

    inner: Agent
    container_name: str
    docker: str
    init_s: float | None = None
    moves: list[dict[str, Any]] = field(default_factory=list)
    stderr_tail: str = ""

    def start(self, init_budget_s: float) -> None:
        started = time.monotonic()
        try:
            self.inner.start(init_budget_s)
        finally:
            self.init_s = time.monotonic() - started

    def move(self, fen: str, time_left_ms: int) -> str:
        started = time.monotonic()
        try:
            move = self.inner.move(fen, time_left_ms)
        except BaseException:
            self.moves.append(
                {
                    "time_left_ms": time_left_ms,
                    "elapsed_ms": round((time.monotonic() - started) * 1000.0, 3),
                    "ok": False,
                }
            )
            raise
        self.moves.append(
            {
                "time_left_ms": time_left_ms,
                "elapsed_ms": round((time.monotonic() - started) * 1000.0, 3),
                "ok": True,
                "move": move,
            }
        )
        return move

    def stop(self) -> None:
        try:
            self.inner.stop()
            self.stderr_tail = self.inner.stderr_tail
        finally:
            # Agent.stop kills the attached docker client.  Remove this one
            # fully resolved, run-scoped container name as a cleanup backstop.
            subprocess.run(
                [self.docker, "rm", "-f", self.container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def timing_summary(agent: TimedAgent) -> dict[str, Any]:
    elapsed = [float(row["elapsed_ms"]) for row in agent.moves]
    ordered = sorted(elapsed)
    if ordered:
        p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
        total = sum(ordered)
        maximum = ordered[-1]
        median = statistics.median(ordered)
        p95 = ordered[p95_index]
    else:
        total = maximum = median = p95 = 0.0
    return {
        "init_s": None if agent.init_s is None else round(agent.init_s, 3),
        "move_count": len(agent.moves),
        "move_total_ms": round(total, 3),
        "move_max_ms": round(maximum, 3),
        "move_median_ms": round(median, 3),
        "move_p95_ms": round(p95, 3),
        "moves": agent.moves,
        "stderr_tail": agent.stderr_tail[-4096:],
    }


def snapshot_archive(path: Path, role: str, snapshot_root: Path) -> ArchiveIdentity:
    """Copy once, then audit/build only the private per-run snapshot."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"not a file: {resolved}")
    snapshot_root.mkdir(parents=True, exist_ok=True)
    snapshot = snapshot_root / f"{role}.zip"
    digest = hashlib.sha256()
    with resolved.open("rb") as source, snapshot.open("xb") as target:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
            target.write(chunk)
    copied_sha = digest.hexdigest()
    manifest = audit(snapshot)
    audited_sha = str(manifest["archive_sha256"])
    if copied_sha != audited_sha:
        raise SystemExit(f"{role} ZIP changed while its run snapshot was created")
    return ArchiveIdentity(
        source_path=resolved,
        snapshot_path=snapshot,
        sha256=audited_sha,
        zip_bytes=int(manifest["zip_bytes"]),
        uncompressed_bytes=int(manifest["uncompressed_bytes"]),
        image_tag=f"{IMAGE_PREFIX}-{role}:{audited_sha[:16]}",
    )


def verify_snapshot(identity: ArchiveIdentity) -> None:
    actual = sha256_path(identity.snapshot_path)
    if actual != identity.sha256:
        raise SystemExit(
            f"{identity.source_path.name} run snapshot no longer matches logged SHA256: "
            f"{actual} != {identity.sha256}"
        )


def safe_extract(archive: Path, destination: Path) -> None:
    """Extract an already-audited archive without merging into stale files."""
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            target = destination.joinpath(*PurePosixPath(info.filename).parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as read, target.open("xb") as write:
                shutil.copyfileobj(read, write)


def build_game_plan(
    fens: tuple[str, ...], pairs: int, opening_offset: int, cpus: tuple[int, int]
) -> tuple[GamePlan, ...]:
    if opening_offset < 0 or opening_offset + pairs > len(fens):
        raise ValueError(
            f"held-out slice [{opening_offset}, {opening_offset + pairs}) exceeds "
            f"the {len(fens)} supplied FENs"
        )
    plans: list[GamePlan] = []
    for pair in range(pairs):
        opening_index = opening_offset + pair
        fen = fens[opening_index]
        # First game: candidate is White on CPU A.  Return game: candidate is
        # Black on CPU B, so colour and physical core both swap.
        plans.extend(
            (
                GamePlan(
                    game=2 * pair + 1,
                    pair=pair + 1,
                    opening_index=opening_index,
                    fen=fen,
                    white_role="candidate",
                    black_role="baseline",
                    white_cpu=cpus[0],
                    black_cpu=cpus[1],
                ),
                GamePlan(
                    game=2 * pair + 2,
                    pair=pair + 1,
                    opening_index=opening_index,
                    fen=fen,
                    white_role="baseline",
                    black_role="candidate",
                    white_cpu=cpus[0],
                    black_cpu=cpus[1],
                ),
            )
        )
    return tuple(plans)


def docker_command(
    docker: str,
    image: str,
    cpu: int,
    container_name: str,
    command: tuple[str, ...] = (),
) -> list[str]:
    return [
        docker,
        "run",
        "--rm",
        "-i",
        "--name",
        container_name,
        "--platform",
        IMAGE_PLATFORM,
        "--cpuset-cpus",
        str(cpu),
        "--cpus",
        "1",
        "--memory",
        CONTAINER_MEMORY,
        "--memory-swap",
        CONTAINER_MEMORY,
        "--network",
        "none",
        "--read-only",
        "--pids-limit",
        "128",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        CONTAINER_TMPFS,
        "--env",
        "HOME=/tmp",
        "--env",
        "NUMBA_CACHE_DIR=/tmp/numba-cache",
        "--env",
        "OMP_NUM_THREADS=1",
        "--env",
        "MKL_NUM_THREADS=1",
        "--env",
        "NUMBA_NUM_THREADS=1",
        image,
        *command,
    ]


def docker_info(docker: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [docker, "info", "--format", "{{json .}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        info = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Docker preflight failed: {exc}") from exc
    if not isinstance(info, dict):
        raise SystemExit("Docker preflight returned no object")
    return info


def preflight_host(
    docker: str, requested_cpus: tuple[int, int] | None
) -> tuple[dict[str, Any], tuple[int, int]]:
    info = docker_info(docker)
    os_name = str(info.get("OSType", "")).lower()
    architecture = str(info.get("Architecture", "")).lower()
    ncpu = int(info.get("NCPU", 0))
    memory = int(info.get("MemTotal", 0))
    if os_name != "linux" or architecture not in {"x86_64", "amd64"}:
        raise SystemExit(
            f"match host must be Linux x86_64; Docker reports {os_name}/{architecture}"
        )
    if ncpu < 2:
        raise SystemExit(f"two dedicated agent cores required; Docker reports {ncpu}")
    if memory < MIN_HOST_MEMORY_BYTES:
        raise SystemExit(
            "host RAM is too small for two simultaneous 2 GB agents plus referee/OS: "
            f"{memory / 1024**3:.2f} GiB reported, 5.00 GiB required"
        )
    available = tuple(range(ncpu))
    cpus = requested_cpus or (available[0], available[1])
    if cpus[0] not in available or cpus[1] not in available:
        raise SystemExit(f"requested CPUs {cpus} are outside Docker's 0..{ncpu - 1}")
    summary = {
        "server_version": info.get("ServerVersion"),
        "os": os_name,
        "architecture": architecture,
        "logical_cpus": ncpu,
        "memory_bytes": memory,
    }
    return summary, cpus


def build_image(
    identity: ArchiveIdentity, role: str, root: Path, docker: str
) -> dict[str, Any]:
    dockerfile = root / "lab" / "docker" / "MatchAgent.Dockerfile"
    runner = root / "harness" / "runner.py"
    probe = root / "lab" / "docker" / "match_image_probe.py"
    runner_sha = sha256_path(runner)
    probe_sha = sha256_path(probe)
    dockerfile_sha = sha256_path(dockerfile)
    verify_snapshot(identity)
    with tempfile.TemporaryDirectory(prefix=f"chess-tk-{role}-") as temporary:
        stage = Path(temporary)
        safe_extract(identity.snapshot_path, stage / "agent")
        verify_snapshot(identity)
        shutil.copy2(runner, stage / "runner.py")
        shutil.copy2(probe, stage / "image_probe.py")
        subprocess.run(
            [
                docker,
                "build",
                "--platform",
                IMAGE_PLATFORM,
                "--label",
                f"org.aichessathon.archive.sha256={identity.sha256}",
                "--label",
                f"org.aichessathon.runner.sha256={runner_sha}",
                "--label",
                f"org.aichessathon.probe.sha256={probe_sha}",
                "--label",
                f"org.aichessathon.dockerfile.sha256={dockerfile_sha}",
                "--label",
                f"org.aichessathon.role={role}",
                "-f",
                str(dockerfile),
                "-t",
                identity.image_tag,
                str(stage),
            ],
            check=True,
        )
    inspected = subprocess.run(
        [docker, "image", "inspect", identity.image_tag, "--format", "{{json .}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    image = json.loads(inspected.stdout)
    labels = image.get("Config", {}).get("Labels", {}) or {}
    if labels.get("org.aichessathon.archive.sha256") != identity.sha256:
        raise SystemExit(f"built {role} image does not carry the exact snapshot SHA256")
    return {
        "tag": identity.image_tag,
        "image_id": image.get("Id"),
        "created": image.get("Created"),
        "os": image.get("Os"),
        "architecture": image.get("Architecture"),
        "runner_sha256": runner_sha,
        "probe_sha256": probe_sha,
        "dockerfile_sha256": dockerfile_sha,
        "archive_sha256_label": labels.get("org.aichessathon.archive.sha256"),
    }


def verify_image_provenance(
    images: Iterable[dict[str, Any]], provenance: dict[str, Any]
) -> None:
    hashes = provenance["files_sha256"]
    expected = {
        "runner_sha256": hashes["harness/runner.py"],
        "probe_sha256": hashes["lab/docker/match_image_probe.py"],
        "dockerfile_sha256": hashes["lab/docker/MatchAgent.Dockerfile"],
    }
    for image in images:
        for field, digest in expected.items():
            if image.get(field) != digest:
                raise SystemExit(
                    f"build input changed during image construction: {field} "
                    f"{image.get(field)!r} != {digest}"
                )


def validate_probe_payload(payload: dict[str, Any], cpu: int) -> list[str]:
    errors: list[str] = []
    if payload.get("python") != "3.12" and not str(payload.get("python", "")).startswith(
        "3.12."
    ):
        errors.append(f"container Python is {payload.get('python')!r}, not 3.12")
    if payload.get("chess") != REQUIRED_CHESS_VERSION:
        errors.append(
            f"container chess is {payload.get('chess')!r}, not {REQUIRED_CHESS_VERSION}"
        )
    if payload.get("numpy") != REQUIRED_NUMPY_VERSION:
        errors.append(
            f"container numpy is {payload.get('numpy')!r}, not {REQUIRED_NUMPY_VERSION}"
        )
    if payload.get("numba") != REQUIRED_NUMBA_VERSION:
        errors.append(
            f"container numba is {payload.get('numba')!r}, not {REQUIRED_NUMBA_VERSION}"
        )
    if str(payload.get("machine", "")).lower() not in {"x86_64", "amd64"}:
        errors.append(f"container machine is {payload.get('machine')!r}, not x86_64")
    if payload.get("core_nb_NUMBA_READY") is not True:
        errors.append("core_nb.NUMBA_READY is not true")
    warmup_s = payload.get("core_nb_WARMUP_S")
    if not isinstance(warmup_s, (int, float)) or warmup_s >= WARMUP_TARGET_S:
        errors.append(f"core_nb.WARMUP_S did not stay below {WARMUP_TARGET_S:.0f}s")
    import_s = payload.get("agent_import_s")
    if not isinstance(import_s, (int, float)) or import_s > COLD_IMPORT_TARGET_S:
        errors.append(
            f"agent cold import did not stay within conservative "
            f"{COLD_IMPORT_TARGET_S:.0f}s target"
        )
    affinity = payload.get("sched_affinity")
    if affinity != [cpu]:
        errors.append(f"effective CPU affinity is {affinity!r}, expected [{cpu}]")
    if payload.get("root_read_only") is not True:
        errors.append("container root was writable")
    if payload.get("tmp_writable") is not True:
        errors.append("container /tmp was not writable")
    if payload.get("tmp_total_bytes") != EXPECTED_TMP_BYTES:
        errors.append(
            f"container /tmp size is {payload.get('tmp_total_bytes')!r}, "
            f"expected {EXPECTED_TMP_BYTES}"
        )
    if payload.get("network_interfaces") != ["lo"]:
        errors.append(
            f"container network interfaces are {payload.get('network_interfaces')!r}, "
            "expected only loopback"
        )

    cgroup = payload.get("cgroup")
    if not isinstance(cgroup, dict):
        errors.append("container exposed no cgroup evidence")
    else:
        version = cgroup.get("version")
        if version not in {1, 2}:
            errors.append(f"unrecognised cgroup version: {version!r}")
        memory_max = cgroup.get("memory_max")
        if not isinstance(memory_max, str) or not memory_max.isdigit():
            errors.append(f"effective memory.max is unavailable: {memory_max!r}")
        elif int(memory_max) != EXPECTED_MEMORY_BYTES:
            errors.append(
                f"effective memory.max is {memory_max}, expected {EXPECTED_MEMORY_BYTES}"
            )
        memory_swap_max = cgroup.get("memory_swap_max")
        expected_swap = 0 if version == 2 else EXPECTED_MEMORY_BYTES
        if not isinstance(memory_swap_max, str) or not memory_swap_max.isdigit():
            errors.append(f"effective swap limit is unavailable: {memory_swap_max!r}")
        elif int(memory_swap_max) != expected_swap:
            errors.append(
                f"effective swap limit is {memory_swap_max}, expected {expected_swap}"
            )
        pids_max = cgroup.get("pids_max")
        if not isinstance(pids_max, str) or not pids_max.isdigit():
            errors.append(f"effective pids.max is unavailable: {pids_max!r}")
        elif int(pids_max) != EXPECTED_PIDS:
            errors.append(f"effective pids.max is {pids_max}, expected {EXPECTED_PIDS}")
        cpu_max = cgroup.get("cpu_max")
        fields = cpu_max.split() if isinstance(cpu_max, str) else []
        if len(fields) != 2 or not all(field.isdigit() for field in fields):
            errors.append(f"effective cpu.max is unavailable: {cpu_max!r}")
        elif abs(int(fields[0]) / max(int(fields[1]), 1) - 1.0) > 0.001:
            errors.append(f"effective cpu.max is not one CPU: {cpu_max}")
        cpuset = cgroup.get("cpuset_cpus_effective")
        if cpuset != str(cpu):
            errors.append(f"effective cgroup cpuset is {cpuset!r}, expected {cpu!r}")
    return errors


def probe_image(
    identity: ArchiveIdentity,
    role: str,
    cpu: int,
    run_id: str,
    docker: str,
) -> dict[str, Any]:
    container_name = f"chess-tk-{run_id.lower()}-{role}-probe"
    command = docker_command(
        docker,
        identity.image_tag,
        cpu,
        container_name,
        ("python", "/harness/image_probe.py"),
    )
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=INIT_BUDGET_S + 5.0,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_stdout = exc.stdout or ""
        timeout_stderr = exc.stderr or ""
        if isinstance(timeout_stdout, bytes):
            timeout_stdout = timeout_stdout.decode("utf-8", "replace")
        if isinstance(timeout_stderr, bytes):
            timeout_stderr = timeout_stderr.decode("utf-8", "replace")
        return {
            "status": "failed",
            "errors": [f"probe exceeded {INIT_BUDGET_S:.0f}s import budget"],
            "wall_s": round(time.monotonic() - started, 3),
            "stdout": timeout_stdout[-4096:],
            "stderr": timeout_stderr[-4096:],
        }
    finally:
        subprocess.run(
            [docker, "rm", "-f", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    wall_s = time.monotonic() - started
    raw_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    payload: dict[str, Any] = {}
    errors: list[str] = []
    if raw_lines:
        try:
            parsed = json.loads(raw_lines[-1])
            if isinstance(parsed, dict):
                payload = parsed
            else:
                errors.append("probe JSON was not an object")
        except json.JSONDecodeError as exc:
            errors.append(f"probe emitted malformed JSON: {exc}")
    else:
        errors.append("probe emitted no JSON")
    errors.extend(validate_probe_payload(payload, cpu))
    if wall_s > COLD_IMPORT_TARGET_S:
        errors.append(
            f"container-to-ready probe wall time exceeded conservative "
            f"{COLD_IMPORT_TARGET_S:.0f}s target"
        )
    if completed.returncode:
        errors.append(f"probe process exited {completed.returncode}")
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "wall_s": round(wall_s, 3),
        "returncode": completed.returncode,
        "evidence": payload,
        "stdout_extra": "\n".join(raw_lines[:-1])[-4096:],
        "stderr": completed.stderr[-4096:],
    }


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")


def role_failed(role: str, plan: GamePlan, result: str, termination: str) -> bool:
    if termination not in FAILED_TERMINATIONS:
        return False
    if termination == "both_failed":
        return True
    role_is_white = plan.white_role == role
    role_lost = result == ("black" if role_is_white else "white")
    return role_lost


def candidate_points(plan: GamePlan, result: str) -> float | None:
    if result == "draw":
        return 0.5
    if result == "void":
        return None
    candidate_is_white = plan.white_role == "candidate"
    return 1.0 if (result == "white") == candidate_is_white else 0.0


def raw_score_summary(
    wins: int, draws: int, losses: int, completed: int
) -> tuple[int, int, float]:
    scored_games = wins + draws + losses
    void_games = completed - scored_games
    if min(wins, draws, losses, completed, void_games) < 0:
        raise ValueError("inconsistent match counters")
    score = (wins + 0.5 * draws) / scored_games if scored_games else 0.0
    return scored_games, void_games, score


def identity_json(identity: ArchiveIdentity) -> dict[str, Any]:
    return {
        "source_path": str(identity.source_path),
        "snapshot_verified": True,
        "sha256": identity.sha256,
        "zip_bytes": identity.zip_bytes,
        "uncompressed_bytes": identity.uncompressed_bytes,
        "image_tag": identity.image_tag,
    }


def dry_run_payload(
    candidate: ArchiveIdentity,
    baseline: ArchiveIdentity,
    plans: Iterable[GamePlan],
    cpus: tuple[int, int],
    arguments: argparse.Namespace,
) -> dict[str, Any]:
    games = []
    for plan in plans:
        identities = {"candidate": candidate, "baseline": baseline}
        white_name = f"dry-g{plan.game}-white"
        black_name = f"dry-g{plan.game}-black"
        games.append(
            {
                **plan.__dict__,
                "white_command": docker_command(
                    arguments.docker,
                    identities[plan.white_role].image_tag,
                    plan.white_cpu,
                    white_name,
                ),
                "black_command": docker_command(
                    arguments.docker,
                    identities[plan.black_role].image_tag,
                    plan.black_cpu,
                    black_name,
                ),
            }
        )
    return {
        "mode": "dry-run",
        "note": "contract-shaped plan; no Docker command was executed",
        "candidate": identity_json(candidate),
        "baseline": identity_json(baseline),
        "cpus": cpus,
        "base_ms": arguments.base_ms,
        "increment_ms": arguments.increment_ms,
        "ply_cap": arguments.ply_cap,
        "opening_offset": arguments.opening_offset,
        "games": games,
    }


def _run_snapshotted(
    arguments: argparse.Namespace, root: Path, snapshot_root: Path
) -> int:
    candidate = snapshot_archive(arguments.candidate, "candidate", snapshot_root)
    baseline = snapshot_archive(arguments.baseline, "baseline", snapshot_root)
    if candidate.sha256 == baseline.sha256:
        raise SystemExit("candidate and baseline ZIPs are byte-identical")
    openings_path = arguments.openings.expanduser().resolve()
    fens = load_openings(openings_path)

    if arguments.dry_run:
        cpus = arguments.cpu_pair or (0, 1)
        plans = build_game_plan(fens, arguments.pairs, arguments.opening_offset, cpus)
        fen_validation = validate_selected_fens(plans)
        payload = dry_run_payload(candidate, baseline, plans, cpus, arguments)
        payload["fen_validation"] = fen_validation
        payload["source_provenance"] = source_provenance(root)
        print(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    runtime = controller_runtime()
    host, cpus = preflight_host(arguments.docker, arguments.cpu_pair)
    plans = build_game_plan(fens, arguments.pairs, arguments.opening_offset, cpus)
    fen_validation = validate_selected_fens(plans)
    log_path = arguments.log.expanduser().resolve()
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    opening_sha = sha256_path(openings_path)

    print(f"building exact candidate ZIP {candidate.sha256}", flush=True)
    candidate_image = build_image(candidate, "candidate", root, arguments.docker)
    print(f"building exact baseline ZIP {baseline.sha256}", flush=True)
    baseline_image = build_image(baseline, "baseline", root, arguments.docker)
    images = {"candidate": candidate, "baseline": baseline}
    provenance = source_provenance(root)
    verify_image_provenance((candidate_image, baseline_image), provenance)

    append_jsonl(
        log_path,
        {
            "type": "run_start",
            "ts": utc_now(),
            "run_id": run_id,
            "fidelity": "published-contract-shaped; tournament CPU unpublished",
            "promotional_evidence": False,
            "assessment": "raw_match_telemetry_only",
            "candidate": identity_json(candidate),
            "baseline": identity_json(baseline),
            "candidate_image": candidate_image,
            "baseline_image": baseline_image,
            "host": host,
            "controller_runtime": runtime,
            "source_provenance": provenance,
            "cpu_pair": cpus,
            "base_ms": arguments.base_ms,
            "increment_ms": arguments.increment_ms,
            "ply_cap": arguments.ply_cap,
            "pairs_planned": arguments.pairs,
            "opening_file": str(openings_path),
            "opening_file_sha256": opening_sha,
            "opening_offset": arguments.opening_offset,
            "fen_validation": fen_validation,
        },
    )

    probes = {
        "candidate": probe_image(candidate, "candidate", cpus[0], run_id, arguments.docker),
        "baseline": probe_image(baseline, "baseline", cpus[1], run_id, arguments.docker),
    }
    for role, probe in probes.items():
        append_jsonl(
            log_path,
            {
                "type": "image_probe",
                "ts": utc_now(),
                "run_id": run_id,
                "role": role,
                "archive_sha256": images[role].sha256,
                "image": images[role].image_tag,
                **probe,
            },
        )
    failed_probes = [role for role, result in probes.items() if result["status"] != "passed"]
    if failed_probes:
        append_jsonl(
            log_path,
            {
                "type": "run_abort",
                "ts": utc_now(),
                "run_id": run_id,
                "reason": "pre_match_image_probe_failed",
                "roles": failed_probes,
                "promotional_evidence": False,
            },
        )
        raise SystemExit("pre-match exact-image probe failed: " + ", ".join(failed_probes))

    started = time.monotonic()
    wins = draws = losses = 0
    terminations: Counter[str] = Counter()
    candidate_failures: Counter[str] = Counter()
    baseline_failures: Counter[str] = Counter()
    completed = 0
    interrupted = False
    try:
        for plan in plans:
            game_token = f"{run_id.lower()}-g{plan.game}"
            white_name = f"chess-tk-{game_token}-w"
            black_name = f"chess-tk-{game_token}-b"
            white_identity = images[plan.white_role]
            black_identity = images[plan.black_role]
            white = TimedAgent(
                Agent(
                    docker_command(
                        arguments.docker,
                        white_identity.image_tag,
                        plan.white_cpu,
                        white_name,
                    )
                ),
                white_name,
                arguments.docker,
            )
            black = TimedAgent(
                Agent(
                    docker_command(
                        arguments.docker,
                        black_identity.image_tag,
                        plan.black_cpu,
                        black_name,
                    )
                ),
                black_name,
                arguments.docker,
            )
            game_started = time.monotonic()
            outcome = play_match(
                white,
                black,
                arguments.base_ms,
                arguments.increment_ms,
                ply_cap=arguments.ply_cap,
                start_fen=plan.fen,
            )
            game_elapsed = time.monotonic() - game_started
            completed += 1
            terminations[outcome.termination] += 1
            points = candidate_points(plan, outcome.result)
            if points == 1.0:
                wins += 1
            elif points == 0.5:
                draws += 1
            elif points == 0.0:
                losses += 1
            failed = role_failed("candidate", plan, outcome.result, outcome.termination)
            baseline_failed = role_failed("baseline", plan, outcome.result, outcome.termination)
            if failed:
                candidate_failures[outcome.termination] += 1
            if baseline_failed:
                baseline_failures[outcome.termination] += 1

            row = {
                "type": "game",
                "ts": utc_now(),
                "run_id": run_id,
                **plan.__dict__,
                "candidate_sha256": candidate.sha256,
                "baseline_sha256": baseline.sha256,
                "white_sha256": white_identity.sha256,
                "black_sha256": black_identity.sha256,
                "white_image": white_identity.image_tag,
                "black_image": black_identity.image_tag,
                "result": outcome.result,
                "termination": outcome.termination,
                "candidate_points": points,
                "candidate_failure": failed,
                "baseline_failure": baseline_failed,
                "elapsed_s": round(game_elapsed, 3),
                "white_timing": timing_summary(white),
                "black_timing": timing_summary(black),
                "pgn": outcome.pgn,
            }
            append_jsonl(log_path, row)
            colour = "white" if plan.white_role == "candidate" else "black"
            print(
                f"game {plan.game}/{len(plans)} pair {plan.pair}: candidate {colour} "
                f"{points} ({outcome.result}, {outcome.termination}) {game_elapsed:.1f}s",
                flush=True,
            )
            if failed and arguments.stop_on_candidate_failure:
                print("stopping after candidate protocol/time failure", flush=True)
                break
    except KeyboardInterrupt:
        interrupted = True
        print("interrupted after current container cleanup", flush=True)

    scored_games, void_games, score = raw_score_summary(wins, draws, losses, completed)
    summary = {
        "type": "run_summary",
        "ts": utc_now(),
        "run_id": run_id,
        "candidate_sha256": candidate.sha256,
        "baseline_sha256": baseline.sha256,
        "games_completed": completed,
        "scored_games": scored_games,
        "void_games": void_games,
        "pairs_completed": completed // 2,
        "interrupted": interrupted,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score": score,
        "score_denominator": "non_void_games",
        "promotional_evidence": False,
        "assessment": "raw_match_telemetry_only; requires a predeclared gate before promotion",
        "terminations": dict(terminations),
        "candidate_failures": dict(candidate_failures),
        "baseline_failures": dict(baseline_failures),
        "wall_s": round(time.monotonic() - started, 3),
    }
    append_jsonl(log_path, summary)
    print(
        f"candidate +{wins} ={draws} -{losses}, score {score:.1%}; "
        f"candidate failures {sum(candidate_failures.values())}, "
        f"baseline failures {sum(baseline_failures.values())}; "
        f"RAW/NON-PROMOTIONAL; log {log_path}",
        flush=True,
    )
    return 1 if candidate_failures or baseline_failures or interrupted else 0


def run(arguments: argparse.Namespace) -> int:
    root = repo_root()
    with tempfile.TemporaryDirectory(prefix="chess-tk-match-snapshots-") as temporary:
        return _run_snapshotted(arguments, root, Path(temporary))


def build_parser() -> argparse.ArgumentParser:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True, help="exact candidate ZIP")
    parser.add_argument("--baseline", type=Path, required=True, help="exact deployed ZIP")
    parser.add_argument("--pairs", type=int, default=DEFAULT_PAIRS)
    parser.add_argument("--base-ms", type=int, default=BASE_MS)
    parser.add_argument("--increment-ms", type=int, default=INCREMENT_MS)
    parser.add_argument("--ply-cap", type=int, default=PLY_CAP)
    parser.add_argument(
        "--openings", type=Path, default=root / "lab" / "openings.fen"
    )
    parser.add_argument(
        "--opening-offset",
        type=int,
        default=DEFAULT_OPENING_OFFSET,
        help="held-out FEN offset; default 100",
    )
    parser.add_argument("--cpu-pair", type=parse_cpu_pair, help="dedicated CPU IDs, e.g. 2,3")
    parser.add_argument("--docker", default="docker")
    parser.add_argument(
        "--log", type=Path, default=root / "lab" / "logs" / "container-match.jsonl"
    )
    parser.add_argument("--dry-run", action="store_true", help="audit ZIPs and print plan only")
    parser.add_argument(
        "--stop-on-candidate-failure",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def main() -> None:
    parser = build_parser()
    arguments = parser.parse_args()
    if arguments.pairs <= 0:
        parser.error("--pairs must be positive")
    if arguments.base_ms <= 0 or arguments.increment_ms < 0 or arguments.ply_cap <= 0:
        parser.error("invalid clock or ply cap")
    if arguments.opening_offset < 0:
        parser.error("--opening-offset must be non-negative")
    raise SystemExit(run(arguments))


if __name__ == "__main__":
    main()
