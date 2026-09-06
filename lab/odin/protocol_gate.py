"""Cold-import/protocol gate against the pinned current official starter."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
PINNED = ROOT / "lab" / "odin" / "official-harness-91f70e54"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="extracted exact candidate source directory")
    parser.add_argument("--cold-target", type=float, default=60.0)
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(PINNED))
    try:
        rules = importlib.import_module("harness.rules")
        sandbox = importlib.import_module("harness.sandbox")
    finally:
        sys.path.pop(0)
    assert Path(rules.__file__).resolve().is_relative_to(PINNED)
    assert rules.PLY_CAP == 600

    bot = sandbox.local(source)
    began = time.perf_counter()
    try:
        bot.start(90.0)
        cold_s = time.perf_counter() - began
        assert cold_s < args.cold_target, ("cold import target", cold_s, args.cold_target)
        probes = (
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "7k/7p/8/8/8/8/P7/K7 b - - 0 300",
            "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
        )
        results = []
        for fen in probes:
            began = time.perf_counter()
            uci = bot.move(fen, 1000)
            elapsed_s = time.perf_counter() - began
            import chess
            assert chess.Move.from_uci(uci) in chess.Board(fen).legal_moves
            assert elapsed_s < 1.0, ("protocol move overrun", uci, elapsed_s)
            results.append({"fen": fen, "move": uci, "elapsed_s": round(elapsed_s, 3)})
    finally:
        bot.stop()
    assert "O5 " in bot.stderr_tail, "missing Odin native telemetry"
    print("ODIN PROTOCOL GATE PASS " + json.dumps({
        "source": str(source), "pinned_harness": str(PINNED),
        "cold_s": round(cold_s, 3), "moves": results,
    }), flush=True)


if __name__ == "__main__":
    main()
