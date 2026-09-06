"""Native smoke gate for an extracted Odin submission source directory.

This deliberately imports the candidate through ``ODIN_SOURCE``.  It is not a
strength test and it never falls back to the historical Storm harness.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ["ODIN_SOURCE"]).resolve()
sys.path.insert(0, str(SOURCE))

import chess  # noqa: E402
import core_nb as core  # noqa: E402
from board_nb import from_fen  # noqa: E402
from movegen_nb import generate_legal, move_uci  # noqa: E402


def main() -> None:
    started = time.perf_counter()
    assert core.warmup() and core.NUMBA_READY
    warmup = core.WARMUP_S

    # Exact rules/state edge positions plus an ordinary tactical position.
    roots = (
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "7k/7p/8/8/8/8/P7/K7 b - - 0 300",
        "8/8/8/8/8/k7/2q5/K7 b - - 0 300",
        "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
    )
    searches: list[dict[str, object]] = []
    for fen in roots:
        assert chess.Board(fen).is_valid(), fen
        pos = from_fen(fen)
        moves = generate_legal(pos)
        began = time.perf_counter()
        choice = core.search_root(pos, moves, 250.0, 120.0, [pos.key], chess.Board(fen).ply())
        elapsed_ms = (time.perf_counter() - began) * 1000.0
        uci = move_uci(choice)
        assert chess.Move.from_uci(uci) in chess.Board(fen).legal_moves
        assert elapsed_ms <= 450.0, ("native deadline overrun", fen, elapsed_ms)
        searches.append({"fen": fen, "move": uci, "elapsed_ms": round(elapsed_ms, 2)})

    # The submission firewall must remain legal at very short clocks.
    import agent  # noqa: E402

    calls: list[dict[str, object]] = []
    for clock_ms in (100, 450, 1000):
        fen = roots[0]
        began = time.perf_counter()
        uci = agent.get_move(fen, clock_ms)
        elapsed_ms = (time.perf_counter() - began) * 1000.0
        assert chess.Move.from_uci(uci) in chess.Board(fen).legal_moves
        assert elapsed_ms < clock_ms, ("agent clock overrun", clock_ms, elapsed_ms)
        calls.append({"clock_ms": clock_ms, "move": uci, "elapsed_ms": round(elapsed_ms, 2)})

    report = {
        "source": str(SOURCE),
        "warmup_s": round(warmup, 3),
        "native_searches": searches,
        "agent_calls": calls,
        "elapsed_s": round(time.perf_counter() - started, 3),
        "note": "Operational gate only; it does not establish playing strength.",
    }
    print("ODIN RELEASE GATE PASS " + json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
