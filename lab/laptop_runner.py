"""Lab-only agent protocol shim for a CPU-pinned Windows laptop match.

The submission archive is never modified.  This process applies the local
resource envelope before importing the cleanly extracted agent, then speaks
the same JSON-lines protocol as :mod:`harness.runner`.

One intentionally documented local-only correction is made after import.  An
older archive may set ``core_nb.NUMBA_READY`` false solely because compilation
took 50 seconds, even though the compiled Numba dispatchers now exist and the
live init budget is 90 seconds.  For a fair laptop comparison we set readiness
true only when both warmed nopython dispatchers prove that compilation
succeeded.  The exact same check is applied to both players and emitted as a
diagnostic on stderr.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import platform
import sys
import time
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any


DIAGNOSTIC_PREFIX = "CHESS_TK_LAPTOP_DIAG "
THREAD_ENV = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMBA_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_HANDLE: int | None = None


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_ulong),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_ulong),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_ulong),
        ("SchedulingClass", ctypes.c_ulong),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def configure_environment(home: Path) -> dict[str, str]:
    if home.exists() and any(home.iterdir()):
        raise RuntimeError(f"isolated runner HOME is not empty: {home}")
    home.mkdir(parents=True, exist_ok=True)
    cache = home / "numba-cache"
    cache.mkdir(parents=True, exist_ok=True)
    temporary = home / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    values = {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "NUMBA_CACHE_DIR": str(cache),
        "TMP": str(temporary),
        "TEMP": str(temporary),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    values.update({name: "1" for name in THREAD_ENV})
    os.environ.update(values)
    # PYTHONDONTWRITEBYTECODE is normally consumed at interpreter startup;
    # setting the runtime flag is what protects this later clean extraction.
    sys.dont_write_bytecode = True
    return values


def _windows_error(prefix: str) -> str:
    code = ctypes.get_last_error()
    return f"{prefix}: winerror {code} ({ctypes.FormatError(code).strip()})"


def apply_windows_affinity(cpu: int) -> dict[str, Any]:
    if os.name != "nt":
        return {"applied": False, "error": "not Windows", "requested_cpu": cpu}
    if cpu < 0 or cpu >= ctypes.sizeof(ctypes.c_size_t) * 8:
        return {
            "applied": False,
            "error": "CPU is outside the current Windows processor group mask",
            "requested_cpu": cpu,
        }
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel32.SetProcessAffinityMask.restype = ctypes.c_int
    kernel32.GetProcessAffinityMask.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.GetProcessAffinityMask.restype = ctypes.c_int
    process = kernel32.GetCurrentProcess()
    requested_mask = 1 << cpu
    if not kernel32.SetProcessAffinityMask(process, ctypes.c_size_t(requested_mask)):
        return {
            "applied": False,
            "error": _windows_error("SetProcessAffinityMask failed"),
            "requested_cpu": cpu,
            "requested_mask": requested_mask,
        }
    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    if not kernel32.GetProcessAffinityMask(
        process, ctypes.byref(process_mask), ctypes.byref(system_mask)
    ):
        return {
            "applied": False,
            "error": _windows_error("GetProcessAffinityMask failed"),
            "requested_cpu": cpu,
            "requested_mask": requested_mask,
        }
    effective = int(process_mask.value)
    return {
        "applied": effective == requested_mask,
        "requested_cpu": cpu,
        "requested_mask": requested_mask,
        "effective_mask": effective,
        "system_mask": int(system_mask.value),
    }


def apply_windows_memory_job(limit_bytes: int) -> dict[str, Any]:
    """Place this process in a 2 GB process/job-memory-limited Job Object."""

    global _JOB_HANDLE
    if os.name != "nt":
        return {"applied": False, "error": "not Windows", "limit_bytes": limit_bytes}
    if limit_bytes <= 0:
        return {"applied": False, "error": "invalid memory limit", "limit_bytes": limit_bytes}

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    kernel32.SetInformationJobObject.restype = ctypes.c_int
    kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.AssignProcessToJobObject.restype = ctypes.c_int
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        return {
            "applied": False,
            "error": _windows_error("CreateJobObjectW failed"),
            "limit_bytes": limit_bytes,
        }
    limits = _JobObjectExtendedLimitInformation()
    limits.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_PROCESS_MEMORY
        | JOB_OBJECT_LIMIT_JOB_MEMORY
        | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    limits.ProcessMemoryLimit = limit_bytes
    limits.JobMemoryLimit = limit_bytes
    if not kernel32.SetInformationJobObject(
        handle,
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    ):
        error = _windows_error("SetInformationJobObject failed")
        kernel32.CloseHandle(handle)
        return {"applied": False, "error": error, "limit_bytes": limit_bytes}
    if not kernel32.AssignProcessToJobObject(handle, kernel32.GetCurrentProcess()):
        error = _windows_error("AssignProcessToJobObject failed")
        kernel32.CloseHandle(handle)
        return {"applied": False, "error": error, "limit_bytes": limit_bytes}

    # Keep the handle alive for the whole agent lifetime.  Closing a Job Object
    # carrying KILL_ON_JOB_CLOSE would otherwise terminate its member.
    _JOB_HANDLE = int(handle)
    return {
        "applied": True,
        "limit_bytes": limit_bytes,
        "limit_kind": "process_and_job_commit",
        "kill_on_job_close": True,
    }


def apply_envelope(cpu: int, memory_limit_bytes: int) -> dict[str, Any]:
    return {
        "affinity": apply_windows_affinity(cpu),
        "memory_job": apply_windows_memory_job(memory_limit_bytes),
    }


def _dispatcher_evidence(module: ModuleType, name: str) -> dict[str, Any]:
    dispatcher = getattr(module, name, None)
    nopython = getattr(dispatcher, "nopython_signatures", ()) if dispatcher is not None else ()
    signatures = getattr(dispatcher, "signatures", ()) if dispatcher is not None else ()
    return {
        "present": dispatcher is not None,
        "nopython_signature_count": len(nopython or ()),
        "signature_count": len(signatures or ()),
    }


def numba_readiness_evidence(
    module: ModuleType | None = None, *, apply_override: bool = True
) -> dict[str, Any]:
    core = sys.modules.get("core_nb") if module is None else module
    if core is None:
        return {
            "module_loaded": False,
            "has_numba": False,
            "compiled": False,
            "original_ready": None,
            "effective_ready": None,
            "override_applied": False,
            "dispatchers": {},
        }
    dispatchers = {
        name: _dispatcher_evidence(core, name) for name in ("perft_nb", "root_search_nb")
    }
    warmup_s = getattr(core, "WARMUP_S", None)
    warmup_completed = bool(
        type(warmup_s) in {int, float} and warmup_s > 0 and math.isfinite(warmup_s)
    )
    compiled = (
        bool(getattr(core, "HAS_NUMBA", False))
        and warmup_completed
        and all(
            evidence["nopython_signature_count"] > 0
            for evidence in dispatchers.values()
        )
    )
    original = getattr(core, "NUMBA_READY", None)
    override = bool(compiled and original is False and apply_override)
    if override:
        setattr(core, "NUMBA_READY", True)
    return {
        "module_loaded": True,
        "has_numba": bool(getattr(core, "HAS_NUMBA", False)),
        "compiled": compiled,
        "warmup_s": warmup_s,
        "warmup_completed": warmup_completed,
        "original_ready": original,
        "effective_ready": getattr(core, "NUMBA_READY", None),
        "override_applied": override,
        "dispatchers": dispatchers,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent_dir", nargs="?", type=Path)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--memory-limit-bytes", type=int, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--envelope-probe", action="store_true")
    parser.add_argument("--strict-envelope", action="store_true")
    return parser


def _envelope_ok(envelope: dict[str, Any]) -> bool:
    return bool(
        envelope.get("affinity", {}).get("applied")
        and envelope.get("memory_job", {}).get("applied")
    )


def main() -> None:
    arguments = build_parser().parse_args()
    configured_env = configure_environment(arguments.home.resolve())
    envelope = apply_envelope(arguments.cpu, arguments.memory_limit_bytes)
    if arguments.envelope_probe:
        print(
            json.dumps(
                {
                    "type": "envelope_probe",
                    "pid": os.getpid(),
                    "platform": platform.platform(),
                    "machine": platform.machine(),
                    "envelope": envelope,
                    "thread_env": {name: configured_env[name] for name in THREAD_ENV},
                },
                sort_keys=True,
            ),
            flush=True,
        )
        raise SystemExit(0 if _envelope_ok(envelope) else 2)

    if arguments.agent_dir is None:
        raise SystemExit("agent_dir is required outside --envelope-probe")

    # Mirror harness.runner exactly: preserve the original stdout as the
    # protocol stream, then redirect fd 1 so agent prints cannot corrupt it.
    protocol = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    if arguments.strict_envelope and not _envelope_ok(envelope):
        print(
            DIAGNOSTIC_PREFIX
            + json.dumps({"type": "laptop_runner_init", "envelope": envelope}),
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(70)

    agent_dir = arguments.agent_dir.resolve()
    os.chdir(agent_dir)
    sys.path.insert(0, str(agent_dir))
    import_started = time.perf_counter()
    agent = import_module("agent")
    import_s = time.perf_counter() - import_started
    numba = numba_readiness_evidence()
    diagnostic = {
        "type": "laptop_runner_init",
        "pid": os.getpid(),
        "cwd": str(agent_dir),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "import_s": round(import_s, 6),
        "envelope": envelope,
        "numba": numba,
        "thread_env": {name: configured_env[name] for name in THREAD_ENV},
        "home": configured_env["HOME"],
        "numba_cache_dir": configured_env["NUMBA_CACHE_DIR"],
    }
    print(
        DIAGNOSTIC_PREFIX + json.dumps(diagnostic, sort_keys=True, default=str),
        file=sys.stderr,
        flush=True,
    )

    protocol.write(json.dumps({"ready": True}) + "\n")
    protocol.flush()
    for line in sys.stdin:
        request = json.loads(line)
        move = agent.get_move(request["fen"], request["time_left_ms"])
        protocol.write(json.dumps({"move": move}) + "\n")
        protocol.flush()


if __name__ == "__main__":
    main()
