"""Emit machine-readable cold-import and effective-cgroup evidence.

This file is copied outside /agent.  It is lab instrumentation and is never
part of a submission ZIP or imported during a game.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

import chess
import numba
import numpy


def _read_first(paths: tuple[str, ...]) -> str | None:
    for name in paths:
        path = Path(name)
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return None


def _root_read_only() -> bool:
    target = Path("/match-probe-write-test")
    try:
        target.write_text("probe", encoding="utf-8")
    except OSError:
        return True
    try:
        target.unlink()
    except OSError:
        pass
    return False


def main() -> None:
    started = time.monotonic()
    # Match runner redirects fd 1 before importing the agent.  Mirror that
    # isolation so agent diagnostics cannot corrupt this JSON protocol line.
    with contextlib.redirect_stdout(sys.stderr):
        importlib.import_module("agent")
        core = importlib.import_module("core_nb")
    import_s = time.monotonic() - started
    numba_ready = getattr(core, "NUMBA_READY", None)
    warmup_s = getattr(core, "WARMUP_S", None)
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None

    tmp_writable = False
    try:
        with tempfile.NamedTemporaryFile(dir="/tmp"):
            tmp_writable = True
    except OSError:
        pass
    tmp_stat = os.statvfs("/tmp")
    cgroup_v2 = Path("/sys/fs/cgroup/cgroup.controllers").is_file()
    try:
        network_interfaces = sorted(path.name for path in Path("/sys/class/net").iterdir())
    except OSError:
        network_interfaces = None

    payload = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "machine": platform.machine(),
        "chess": chess.__version__,
        "numpy": numpy.__version__,
        "numba": numba.__version__,
        "agent_import_s": round(import_s, 6),
        "core_nb_NUMBA_READY": numba_ready,
        "core_nb_WARMUP_S": warmup_s,
        "sched_affinity": affinity,
        "root_read_only": _root_read_only(),
        "tmp_writable": tmp_writable,
        "tmp_total_bytes": tmp_stat.f_frsize * tmp_stat.f_blocks,
        "network_interfaces": network_interfaces,
        "cgroup": {
            "version": 2 if cgroup_v2 else 1,
            "cpu_max": _read_first(("/sys/fs/cgroup/cpu.max",)),
            "cpuset_cpus_effective": _read_first(
                ("/sys/fs/cgroup/cpuset.cpus.effective", "/sys/fs/cgroup/cpuset/cpuset.cpus")
            ),
            "memory_max": _read_first(
                ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes")
            ),
            "memory_swap_max": _read_first(
                (
                    "/sys/fs/cgroup/memory.swap.max",
                    "/sys/fs/cgroup/memory/memory.memsw.limit_in_bytes",
                )
            ),
            "pids_max": _read_first(
                ("/sys/fs/cgroup/pids.max", "/sys/fs/cgroup/pids/pids.max")
            ),
        },
    }
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True), flush=True)
    if numba_ready is not True:
        raise SystemExit("core_nb.NUMBA_READY is not true")


if __name__ == "__main__":
    main()
