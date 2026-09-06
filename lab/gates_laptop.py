"""One-command laptop gate bundle (no agent import — avoids Numba JIT hang).

Run: python -m lab.gates_laptop
"""

from __future__ import annotations

import subprocess
import sys


def _run(module: str, *args: str) -> None:
    cmd = [sys.executable, "-m", module, *args]
    print(f">>> {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def main() -> None:
    _run("lab.perft", "--quick")
    _run("lab.test_c")
    _run("lab.test_time")
    _run("lab.test_node_budget")
    _run("lab.test_iteration_start")
    _run("lab.test_tb")
    _run("lab.referee_smoke")
    print("LAPTOP GATES OK")


if __name__ == "__main__":
    main()
