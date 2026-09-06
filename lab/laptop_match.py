"""Run a competition-clocked paired match on this Windows laptop.

This is the closest useful local simulation, not platform proof.  It uses the
untouched official referee/rules, exact snapshotted ZIP bytes, a fresh clean
extraction and fresh process for every player in every game, one Windows
logical CPU per player, a 2 GB Job Object memory cap, and the published
120 s + 0.5 s / 300-ply defaults.  Paired games reuse a FEN while swapping the
candidate's colour and logical CPU.

Important differences are recorded in every run: Windows ARM64 rather than
Linux x86-64, writable clean snapshots rather than a read-only container,
local held-out openings, no per-process network namespace, and a lab-only
runner shim that repairs the obsolete post-compilation readiness cutoff
equally for both archives.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import sysconfig
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
from lab.laptop_runner import DIAGNOSTIC_PREFIX, THREAD_ENV
from lab.release_audit import audit


MEMORY_LIMIT_BYTES = 2 * 1024**3
DEFAULT_PAIRS = 10
DEFAULT_OPENING_OFFSET = 100
REQUIRED_VERSIONS = {
    "chess": "1.11.2",
    "numpy": "2.5.2",
    "numba": "0.67.0",
    "llvmlite": "0.49.0",
}
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010


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


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")


@dataclass(frozen=True)
class ArchiveSnapshot:
    role: str
    source_path: Path
    snapshot_path: Path
    sha256: str
    zip_bytes: int
    uncompressed_bytes: int
    entries: tuple[dict[str, Any], ...]


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


def snapshot_archive(path: Path, role: str, destination: Path) -> ArchiveSnapshot:
    source_path = path.expanduser().resolve()
    if not source_path.is_file():
        raise SystemExit(f"{role} ZIP not found: {source_path}")
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_path = destination / f"{role}.zip"
    digest = hashlib.sha256()
    with source_path.open("rb") as source, snapshot_path.open("xb") as target:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
            target.write(chunk)
    copied_sha = digest.hexdigest()
    manifest = audit(snapshot_path)
    audited_sha = str(manifest["archive_sha256"])
    if copied_sha != audited_sha:
        raise SystemExit(f"{role} ZIP changed while its private snapshot was copied")
    return ArchiveSnapshot(
        role=role,
        source_path=source_path,
        snapshot_path=snapshot_path,
        sha256=audited_sha,
        zip_bytes=int(manifest["zip_bytes"]),
        uncompressed_bytes=int(manifest["uncompressed_bytes"]),
        entries=tuple(manifest["entries"]),
    )


def verify_snapshot(snapshot: ArchiveSnapshot) -> None:
    actual = sha256_path(snapshot.snapshot_path)
    if actual != snapshot.sha256:
        raise SystemExit(
            f"{snapshot.role} private snapshot changed: {actual} != {snapshot.sha256}"
        )


def safe_extract(snapshot: ArchiveSnapshot, destination: Path) -> None:
    verify_snapshot(snapshot)
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(snapshot.snapshot_path) as archive:
        for info in archive.infolist():
            target = destination.joinpath(*PurePosixPath(info.filename).parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    problems = extraction_problems(snapshot, destination)
    if problems:
        raise SystemExit(f"clean extraction verification failed: {'; '.join(problems)}")


def extraction_problems(snapshot: ArchiveSnapshot, destination: Path) -> list[str]:
    expected = {str(entry["name"]): str(entry["sha256"]) for entry in snapshot.entries}
    actual = {
        path.relative_to(destination).as_posix(): sha256_path(path)
        for path in destination.rglob("*")
        if path.is_file()
    }
    problems: list[str] = []
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])
    if missing:
        problems.append("missing: " + ", ".join(missing))
    if extra:
        problems.append("extra: " + ", ".join(extra))
    if changed:
        problems.append("changed: " + ", ".join(changed))
    return problems


def snapshot_json(snapshot: ArchiveSnapshot) -> dict[str, Any]:
    return {
        "source_path": str(snapshot.source_path),
        "sha256": snapshot.sha256,
        "zip_bytes": snapshot.zip_bytes,
        "uncompressed_bytes": snapshot.uncompressed_bytes,
        "entry_count": len(snapshot.entries),
        "private_snapshot_verified": True,
    }


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


def build_game_plan(
    fens: tuple[str, ...], pairs: int, opening_offset: int, cpus: tuple[int, int]
) -> tuple[GamePlan, ...]:
    if pairs <= 0:
        raise ValueError("pairs must be positive")
    if opening_offset < 0 or opening_offset + pairs > len(fens):
        raise ValueError(
            f"opening slice [{opening_offset}, {opening_offset + pairs}) exceeds "
            f"the {len(fens)} supplied FENs"
        )
    plans: list[GamePlan] = []
    for pair_offset in range(pairs):
        opening_index = opening_offset + pair_offset
        common = {
            "pair": pair_offset + 1,
            "opening_index": opening_index,
            "fen": fens[opening_index],
            "white_cpu": cpus[0],
            "black_cpu": cpus[1],
        }
        plans.append(
            GamePlan(
                game=pair_offset * 2 + 1,
                white_role="candidate",
                black_role="baseline",
                **common,
            )
        )
        plans.append(
            GamePlan(
                game=pair_offset * 2 + 2,
                white_role="baseline",
                black_role="candidate",
                **common,
            )
        )
    return tuple(plans)


def validate_fens(plans: Iterable[GamePlan]) -> dict[str, Any]:
    selected: dict[int, str] = {}
    for plan in plans:
        selected[plan.opening_index] = plan.fen
    for index, fen in sorted(selected.items()):
        try:
            board = chess.Board(fen)
        except ValueError as exc:
            raise SystemExit(f"invalid FEN at opening {index}: {exc}") from exc
        if not board.is_valid() or board.outcome(claim_draw=True) is not None:
            raise SystemExit(f"opening {index} is invalid or already terminal: {fen}")
    digest = hashlib.sha256()
    for index, fen in sorted(selected.items()):
        digest.update(f"{index}\0{fen}\n".encode())
    return {
        "count": len(selected),
        "indices": sorted(selected),
        "selection_sha256": digest.hexdigest(),
        "all_valid_nonterminal": True,
    }


def parse_cpu_pair(value: str) -> tuple[int, int]:
    try:
        items = tuple(int(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("CPU pair must be e.g. 0,1") from exc
    if len(items) != 2 or min(items) < 0 or items[0] == items[1]:
        raise argparse.ArgumentTypeError("CPU pair must be two distinct non-negative IDs")
    return items[0], items[1]


def windows_available_cpus() -> tuple[int, ...]:
    if os.name != "nt":
        raise SystemExit("the laptop match runner requires Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.GetProcessAffinityMask.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.GetProcessAffinityMask.restype = ctypes.c_int
    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    if not kernel32.GetProcessAffinityMask(
        kernel32.GetCurrentProcess(), ctypes.byref(process_mask), ctypes.byref(system_mask)
    ):
        raise SystemExit(f"cannot query Windows affinity mask: {ctypes.get_last_error()}")
    return tuple(
        index
        for index in range(ctypes.sizeof(ctypes.c_size_t) * 8)
        if int(process_mask.value) & (1 << index)
    )


def runtime_metadata(*, enforce: bool = True) -> dict[str, Any]:
    packages: dict[str, str] = {}
    for distribution in REQUIRED_VERSIONS:
        try:
            packages[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            packages[distribution] = "missing"
    errors: list[str] = []
    if sys.version_info[:2] != (3, 12):
        errors.append(f"Python is {platform.python_version()}, expected 3.12.x")
    for name, required in REQUIRED_VERSIONS.items():
        if packages[name] != required:
            errors.append(f"{name} is {packages[name]}, expected {required}")
    result = {
        "python": platform.python_version(),
        "executable": sys.executable,
        "implementation": platform.python_implementation(),
        "compiler": platform.python_compiler(),
        "sysconfig_platform": sysconfig.get_platform(),
        "os_platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": packages,
        "competition_versions_match": not errors,
        "errors": errors,
    }
    if enforce and errors:
        raise SystemExit("runtime preflight failed:\n- " + "\n- ".join(errors))
    return result


def source_provenance(root: Path) -> dict[str, Any]:
    files = (
        "harness/referee.py",
        "harness/rules.py",
        "harness/sandbox.py",
        "harness/runner.py",
        "lab/laptop_runner.py",
        "lab/laptop_match.py",
        "lab/paired_match_stats.py",
        "lab/openings.fen",
        "lab/STARTER_SHA",
    )
    missing = [name for name in files if not (root / name).is_file()]
    if missing:
        raise SystemExit("provenance files missing: " + ", ".join(missing))
    return {
        "starter_commit": (root / "lab" / "STARTER_SHA").read_text(encoding="utf-8").strip(),
        "files_sha256": {name: sha256_path(root / name) for name in files},
    }


def runner_command(
    extracted: Path, home: Path, cpu: int, memory_limit_bytes: int
) -> list[str]:
    return [
        sys.executable,
        "-B",
        "-u",
        str(Path(__file__).with_name("laptop_runner.py")),
        str(extracted),
        "--cpu",
        str(cpu),
        "--memory-limit-bytes",
        str(memory_limit_bytes),
        "--home",
        str(home),
        "--strict-envelope",
    ]


def probe_envelope(cpu: int, home: Path, memory_limit_bytes: int) -> dict[str, Any]:
    command = [
        sys.executable,
        "-B",
        "-u",
        str(Path(__file__).with_name("laptop_runner.py")),
        "--cpu",
        str(cpu),
        "--memory-limit-bytes",
        str(memory_limit_bytes),
        "--home",
        str(home),
        "--envelope-probe",
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10.0,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"CPU {cpu} envelope probe emitted invalid JSON: {exc}") from exc
    payload["returncode"] = completed.returncode
    payload["stderr"] = completed.stderr[-4096:]
    envelope = payload.get("envelope", {})
    if (
        completed.returncode != 0
        or envelope.get("affinity", {}).get("applied") is not True
        or envelope.get("memory_job", {}).get("applied") is not True
    ):
        raise SystemExit(f"CPU {cpu} cannot enforce the laptop envelope: {payload}")
    return payload


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def query_process_memory(pid: int) -> dict[str, int] | None:
    if os.name != "nt":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_ProcessMemoryCountersEx),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid
    )
    if not handle:
        return None
    try:
        counters = _ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), ctypes.sizeof(counters)
        ):
            return None
        return {
            "working_set_bytes": int(counters.WorkingSetSize),
            "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
            "private_bytes": int(counters.PrivateUsage),
            "pagefile_bytes": int(counters.PagefileUsage),
        }
    finally:
        kernel32.CloseHandle(handle)


def parse_runner_diagnostics(stderr: str) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for line in stderr.splitlines():
        if not line.startswith(DIAGNOSTIC_PREFIX):
            continue
        try:
            payload = json.loads(line[len(DIAGNOSTIC_PREFIX) :])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            diagnostics.append(payload)
    return diagnostics


@dataclass
class TimedLaptopAgent:
    inner: Agent
    role: str
    cpu: int
    init_s: float | None = None
    moves: list[dict[str, Any]] = field(default_factory=list)
    memory_samples: list[dict[str, Any]] = field(default_factory=list)
    stderr_tail: str = ""
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def _sample_memory(self, phase: str) -> None:
        process = getattr(self.inner, "_process", None)
        if process is None:
            return
        sample = query_process_memory(process.pid)
        if sample is not None:
            self.memory_samples.append({"phase": phase, "pid": process.pid, **sample})

    def start(self, init_budget_s: float) -> None:
        started = time.monotonic()
        try:
            self.inner.start(init_budget_s)
        finally:
            self.init_s = time.monotonic() - started
            self._sample_memory("after_init")

    def move(self, fen: str, time_left_ms: int) -> str:
        move_number = len(self.moves) + 1
        started = time.monotonic()
        try:
            move = self.inner.move(fen, time_left_ms)
        except BaseException:
            self.moves.append(
                {
                    "request": move_number,
                    "time_left_ms": time_left_ms,
                    "elapsed_ms": round((time.monotonic() - started) * 1000.0, 3),
                    "ok": False,
                }
            )
            raise
        self.moves.append(
            {
                "request": move_number,
                "time_left_ms": time_left_ms,
                "elapsed_ms": round((time.monotonic() - started) * 1000.0, 3),
                "ok": True,
                "move": move,
            }
        )
        return move

    def stop(self) -> None:
        self._sample_memory("before_stop")
        self.inner.stop()
        self.stderr_tail = self.inner.stderr_tail
        self.diagnostics = parse_runner_diagnostics(self.stderr_tail)


def timing_summary(agent: TimedLaptopAgent) -> dict[str, Any]:
    elapsed = sorted(float(row["elapsed_ms"]) for row in agent.moves)
    if elapsed:
        p95_index = max(0, math.ceil(0.95 * len(elapsed)) - 1)
        total = sum(elapsed)
        maximum = elapsed[-1]
        median = statistics.median(elapsed)
        p95 = elapsed[p95_index]
    else:
        total = maximum = median = p95 = 0.0
    max_peak = max(
        (int(row["peak_working_set_bytes"]) for row in agent.memory_samples), default=0
    )
    max_private = max((int(row["private_bytes"]) for row in agent.memory_samples), default=0)
    return {
        "role": agent.role,
        "cpu": agent.cpu,
        "init_s": None if agent.init_s is None else round(agent.init_s, 3),
        "move_count": len(agent.moves),
        "move_total_ms": round(total, 3),
        "move_max_ms": round(maximum, 3),
        "move_median_ms": round(median, 3),
        "move_p95_ms": round(p95, 3),
        "moves": agent.moves,
        "memory_observed": {
            "max_peak_working_set_bytes": max_peak,
            "max_private_bytes": max_private,
            "samples": agent.memory_samples,
            "sampling_note": "sampled around init/moves; Job Object enforces the hard cap",
        },
        "runner_diagnostics": agent.diagnostics,
        "stderr_tail": agent.stderr_tail[-4096:],
    }


def role_failed(role: str, plan: GamePlan, result: str, termination: str) -> bool:
    if termination not in FAILED_TERMINATIONS:
        return False
    if termination == "both_failed":
        return True
    role_is_white = plan.white_role == role
    return result == ("black" if role_is_white else "white")


def candidate_points(plan: GamePlan, result: str) -> float | None:
    if result == "draw":
        return 0.5
    if result == "void":
        return None
    return 1.0 if (result == "white") == (plan.white_role == "candidate") else 0.0


def dry_run_payload(
    candidate: ArchiveSnapshot,
    baseline: ArchiveSnapshot,
    plans: tuple[GamePlan, ...],
    cpus: tuple[int, int],
    arguments: argparse.Namespace,
    runtime: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "dry-run",
        "fidelity": "Windows laptop simulation; not platform proof",
        "candidate": snapshot_json(candidate),
        "baseline": snapshot_json(baseline),
        "runtime": runtime,
        "source_provenance": provenance,
        "cpu_pair": cpus,
        "memory_limit_bytes_per_agent": MEMORY_LIMIT_BYTES,
        "base_ms": arguments.base_ms,
        "increment_ms": arguments.increment_ms,
        "ply_cap": arguments.ply_cap,
        "games": [plan.__dict__ for plan in plans],
    }


def limitations(runtime: dict[str, Any]) -> list[str]:
    return [
        "Windows ARM64 host, not the competition's Linux x86-64 host",
        f"local interpreter platform is {runtime['sysconfig_platform']} on {runtime['machine']}",
        "tournament CPU model and load are unpublished",
        "clean writable extraction per process substitutes for a read-only container root",
        "HOME/cache/temp are isolated but the temp directory has no 256 MB filesystem quota",
        "per-process network is not disabled on Windows; neither archive is granted extra data",
        "openings are the pre-existing held-out local set, not tournament-private positions",
        "lab runner applies the same compiled-Numba readiness correction to both archives",
    ]


def runner_diagnostic_problems(
    diagnostics: list[dict[str, Any]],
    *,
    expected_cpu: int,
    expected_memory_limit: int = MEMORY_LIMIT_BYTES,
) -> list[str]:
    """Reject an unenforced envelope or either engine's Python fallback."""

    if not diagnostics:
        return ["emitted no runner diagnostic"]
    latest = diagnostics[-1]
    problems: list[str] = []
    envelope = latest.get("envelope", {})
    affinity = envelope.get("affinity", {})
    if affinity.get("applied") is not True:
        problems.append("did not enforce single-CPU affinity")
    if affinity.get("requested_cpu") != expected_cpu:
        problems.append(f"requested CPU is not {expected_cpu}")
    if affinity.get("effective_mask") != 1 << expected_cpu:
        problems.append(f"effective affinity mask is not CPU {expected_cpu} alone")
    memory_job = envelope.get("memory_job", {})
    if memory_job.get("applied") is not True:
        problems.append("did not enforce the 2 GB Job Object limit")
    if memory_job.get("limit_bytes") != expected_memory_limit:
        problems.append(f"memory limit is not {expected_memory_limit} bytes")
    thread_env = latest.get("thread_env", {})
    wrong_threads = [name for name in THREAD_ENV if thread_env.get(name) != "1"]
    if wrong_threads:
        problems.append("thread limits are not one for: " + ", ".join(wrong_threads))
    numba = latest.get("numba", {})
    if numba.get("compiled") is not True:
        problems.append("did not prove warmed nopython dispatchers")
    if numba.get("effective_ready") is not True:
        problems.append("would use the Python fallback instead of Numba")
    return problems


def _run_snapshots(
    arguments: argparse.Namespace, root: Path, temporary_root: Path
) -> int:
    snapshot_dir = temporary_root / "snapshots"
    candidate = snapshot_archive(arguments.candidate, "candidate", snapshot_dir)
    baseline = snapshot_archive(arguments.baseline, "baseline", snapshot_dir)
    if candidate.sha256 == baseline.sha256:
        raise SystemExit("candidate and baseline ZIPs are byte-identical")

    runtime = runtime_metadata(enforce=not arguments.dry_run)
    provenance = source_provenance(root)
    fens = load_openings(arguments.openings.expanduser().resolve())
    available = windows_available_cpus()
    if len(available) < 2:
        raise SystemExit(f"need two logical CPUs; current process may use {available}")
    cpus = arguments.cpu_pair or (available[0], available[1])
    if cpus[0] not in available or cpus[1] not in available:
        raise SystemExit(f"requested CPUs {cpus} are outside available set {available}")
    plans = build_game_plan(fens, arguments.pairs, arguments.opening_offset, cpus)
    fen_validation = validate_fens(plans)

    if arguments.dry_run:
        payload = dry_run_payload(
            candidate, baseline, plans, cpus, arguments, runtime, provenance
        )
        payload["fen_validation"] = fen_validation
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    probes = {
        str(cpu): probe_envelope(
            cpu, temporary_root / f"probe-home-cpu-{cpu}", MEMORY_LIMIT_BYTES
        )
        for cpu in cpus
    }
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    log_path = arguments.log.expanduser().resolve()
    append_jsonl(
        log_path,
        {
            "type": "run_start",
            "ts": utc_now(),
            "run_id": run_id,
            "fidelity": "competition-clocked Windows laptop simulation; not platform proof",
            "promotional_evidence": False,
            "candidate": snapshot_json(candidate),
            "baseline": snapshot_json(baseline),
            "runtime": runtime,
            "source_provenance": provenance,
            "limitations": limitations(runtime),
            "official_referee_unchanged": True,
            "runner_shim": "lab/laptop_runner.py",
            "runner_shim_applied_identically": True,
            "fresh_process_and_clean_extraction_per_player_per_game": True,
            "cpu_pair": cpus,
            "available_cpus": available,
            "memory_limit_bytes_per_agent": MEMORY_LIMIT_BYTES,
            "memory_enforcement": "Windows Job Object process and job commit limit",
            "envelope_probes": probes,
            "thread_env": {name: "1" for name in THREAD_ENV},
            "base_ms": arguments.base_ms,
            "increment_ms": arguments.increment_ms,
            "ply_cap": arguments.ply_cap,
            "init_budget_s": INIT_BUDGET_S,
            "pairs_planned": arguments.pairs,
            "opening_file": str(arguments.openings.expanduser().resolve()),
            "opening_offset": arguments.opening_offset,
            "fen_validation": fen_validation,
        },
    )

    identities = {"candidate": candidate, "baseline": baseline}
    wins = draws = losses = completed = 0
    terminations: Counter[str] = Counter()
    candidate_failures: Counter[str] = Counter()
    baseline_failures: Counter[str] = Counter()
    config_problems: list[str] = []
    interrupted = False
    started = time.monotonic()
    try:
        for plan in plans:
            game_root = temporary_root / f"game-{plan.game:04d}"
            game_root.mkdir()
            white_snapshot = identities[plan.white_role]
            black_snapshot = identities[plan.black_role]
            white_dir = game_root / "white-agent"
            black_dir = game_root / "black-agent"
            safe_extract(white_snapshot, white_dir)
            safe_extract(black_snapshot, black_dir)
            white = TimedLaptopAgent(
                Agent(
                    runner_command(
                        white_dir,
                        game_root / "white-home",
                        plan.white_cpu,
                        MEMORY_LIMIT_BYTES,
                    )
                ),
                role=plan.white_role,
                cpu=plan.white_cpu,
            )
            black = TimedLaptopAgent(
                Agent(
                    runner_command(
                        black_dir,
                        game_root / "black-home",
                        plan.black_cpu,
                        MEMORY_LIMIT_BYTES,
                    )
                ),
                role=plan.black_role,
                cpu=plan.black_cpu,
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
            points = candidate_points(plan, outcome.result)
            if points == 1.0:
                wins += 1
            elif points == 0.5:
                draws += 1
            elif points == 0.0:
                losses += 1
            terminations[outcome.termination] += 1
            candidate_failed = role_failed(
                "candidate", plan, outcome.result, outcome.termination
            )
            baseline_failed = role_failed(
                "baseline", plan, outcome.result, outcome.termination
            )
            if candidate_failed:
                candidate_failures[outcome.termination] += 1
            if baseline_failed:
                baseline_failures[outcome.termination] += 1

            post_problems = {
                "white": extraction_problems(white_snapshot, white_dir),
                "black": extraction_problems(black_snapshot, black_dir),
            }
            for colour, problems in post_problems.items():
                if problems:
                    config_problems.append(
                        f"game {plan.game} {colour} modified clean extraction: {problems}"
                    )
            white_timing = timing_summary(white)
            black_timing = timing_summary(black)
            for colour, timing in (("white", white_timing), ("black", black_timing)):
                diagnostics = timing["runner_diagnostics"]
                diagnostic_problems = runner_diagnostic_problems(
                    diagnostics, expected_cpu=int(timing["cpu"])
                )
                if diagnostic_problems:
                    config_problems.append(
                        f"game {plan.game} {colour}: " + "; ".join(diagnostic_problems)
                    )

            append_jsonl(
                log_path,
                {
                    "type": "game",
                    "ts": utc_now(),
                    "run_id": run_id,
                    **plan.__dict__,
                    "candidate_colour": (
                        "white" if plan.white_role == "candidate" else "black"
                    ),
                    "candidate_sha256": candidate.sha256,
                    "baseline_sha256": baseline.sha256,
                    "white_sha256": white_snapshot.sha256,
                    "black_sha256": black_snapshot.sha256,
                    "result": outcome.result,
                    "termination": outcome.termination,
                    "candidate_points": points,
                    "candidate_failure": candidate_failed,
                    "baseline_failure": baseline_failed,
                    "elapsed_s": round(game_elapsed, 3),
                    "white_timing": white_timing,
                    "black_timing": black_timing,
                    "post_game_archive_files_unchanged": not any(post_problems.values()),
                    "post_game_extraction_problems": post_problems,
                    "pgn": outcome.pgn,
                },
            )
            colour = "white" if plan.white_role == "candidate" else "black"
            print(
                f"game {plan.game}/{len(plans)} pair {plan.pair}: candidate {colour} "
                f"{points} ({outcome.result}, {outcome.termination}) {game_elapsed:.1f}s",
                flush=True,
            )
            resolved_game_root = game_root.resolve()
            if resolved_game_root.parent != temporary_root.resolve():
                raise RuntimeError(f"refusing to remove unexpected game path {resolved_game_root}")
            shutil.rmtree(resolved_game_root)
            if candidate_failed and arguments.stop_on_candidate_failure:
                print("stopping after candidate protocol/time failure", flush=True)
                break
            if config_problems:
                print("stopping because the simulated envelope lost integrity", flush=True)
                break
    except KeyboardInterrupt:
        interrupted = True
        print("interrupted; completed games remain in the log", flush=True)

    scored = wins + draws + losses
    score = (wins + 0.5 * draws) / scored if scored else 0.0
    summary = {
        "type": "run_summary",
        "ts": utc_now(),
        "run_id": run_id,
        "candidate_sha256": candidate.sha256,
        "baseline_sha256": baseline.sha256,
        "games_completed": completed,
        "pairs_completed": completed // 2,
        "scored_games": scored,
        "void_games": completed - scored,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score": score,
        "terminations": dict(terminations),
        "candidate_failures": dict(candidate_failures),
        "baseline_failures": dict(baseline_failures),
        "configuration_problems": config_problems,
        "interrupted": interrupted,
        "wall_s": round(time.monotonic() - started, 3),
        "fidelity": "competition-clocked Windows laptop simulation; not platform proof",
        "promotional_evidence": False,
    }
    append_jsonl(log_path, summary)
    print(
        f"candidate +{wins} ={draws} -{losses}, score {score:.1%}; "
        f"candidate failures {sum(candidate_failures.values())}; log {log_path}",
        flush=True,
    )
    if config_problems:
        print("CONFIGURATION FAILURE: " + "; ".join(config_problems), flush=True)
    return 1 if candidate_failures or baseline_failures or config_problems or interrupted else 0


def run(arguments: argparse.Namespace) -> int:
    root = repo_root()
    with tempfile.TemporaryDirectory(prefix="chess-tk-laptop-match-") as temporary:
        return _run_snapshots(arguments, root, Path(temporary))


def build_parser() -> argparse.ArgumentParser:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True, help="exact candidate ZIP")
    parser.add_argument("--baseline", type=Path, required=True, help="exact deployed ZIP")
    parser.add_argument("--pairs", type=int, default=DEFAULT_PAIRS)
    parser.add_argument("--base-ms", type=int, default=BASE_MS)
    parser.add_argument("--increment-ms", type=int, default=INCREMENT_MS)
    parser.add_argument("--ply-cap", type=int, default=PLY_CAP)
    parser.add_argument("--openings", type=Path, default=root / "lab" / "openings.fen")
    parser.add_argument("--opening-offset", type=int, default=DEFAULT_OPENING_OFFSET)
    parser.add_argument("--cpu-pair", type=parse_cpu_pair, help="logical CPU IDs, e.g. 0,1")
    parser.add_argument(
        "--log", type=Path, default=root / "lab" / "logs" / "laptop-match.jsonl"
    )
    parser.add_argument("--dry-run", action="store_true", help="audit and print the plan only")
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
