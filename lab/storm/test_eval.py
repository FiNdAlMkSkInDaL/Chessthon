"""Evaluation correctness gates and whole-search/evaluator overhead screening.

Use --bench --engine storm for the unchanged r2 comparator. The isolated r3
tree additionally runs independent positional-evaluation invariants. No engine
source or heuristic parameter is changed by this driver.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=Path, default=ROOT / "dist/storm-eval-r3")
    parser.add_argument("--bench", action="store_true")
    parser.add_argument("--cpu", type=int, default=6)
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    assert kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), 1 << args.cpu)
    sys.path.insert(0, str(args.engine.resolve()))
    import chess
    import numpy as np
    from numba import njit
    import core_nb as c
    from board_nb import from_fen
    import test_eval_design as design
    import test_selectivity as selective

    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.engine.glob("*.py")}
    report = {"engine": str(args.engine.resolve()), "source_sha256": hashes, "cpu": args.cpu}
    if args.bench:
        assert c.warmup() and c.NUMBA_READY
        report["warmup_s"] = c.WARMUP_S
        print("warmup", round(c.WARMUP_S, 3), flush=True)
    if hasattr(c, "positional_terms_nb"):
        design.test_pawn_attack_geometry(c, np, chess)
        invariant_report = design.test_passers(c, chess)
        boards = design.corpus(chess)
        invariant_report.update(design.test_eval_invariants(c, np, chess, boards))
        invariant_report.update(design.test_make_unmake_evaluation(c, np, chess, boards))
        report["invariants"] = invariant_report
        print("EVAL INVARIANTS PASS", json.dumps(invariant_report), flush=True)
    if args.bench:
        fens = selective.bench_fens(args.count)
        positions = []
        for index, fen in enumerate(fens, 1):
            result = selective.run_position(c, np, fen, args.depth)
            positions.append(result)
            print(index, result["move"], result["score"], result["nodes"],
                  round(result["seconds"], 3), flush=True)
        report.update({"depth": args.depth, "positions": positions,
                       "nodes": sum(p["nodes"] for p in positions),
                       "seconds": sum(p["seconds"] for p in positions)})
        packed = [c.pack_pos(from_fen(fen)) for fen in fens]
        bb_batch = np.stack([p[0] for p in packed])
        st_batch = np.stack([p[2] for p in packed])
        evaluator = c.evaluate_nb

        @njit(cache=False)
        def sum_evaluations(boards, states, repeat):
            total = 0
            for _ in range(repeat):
                for i in range(len(boards)):
                    total += evaluator(boards[i], states[i], 0)
            return total

        sum_evaluations(bb_batch, st_batch, 1)
        elapsed = []
        repeat = 1000
        checksum = 0
        for _ in range(3):
            before = time.perf_counter()
            checksum = int(sum_evaluations(bb_batch, st_batch, repeat))
            elapsed.append(time.perf_counter() - before)
        report["evaluation_microbenchmark"] = {
            "evaluations_per_sample": repeat * len(fens), "seconds": elapsed,
            "median_ns_per_evaluation": sorted(elapsed)[1] * 1e9 / (repeat * len(fens)),
            "checksum": checksum,
            "note": "Cached-position microbenchmark. Whole-search wall time and matches remain the relevant gates.",
        }
    report["source_unchanged"] = hashes == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.engine.glob("*.py")
    }
    assert report["source_unchanged"]
    report["note"] = "Windows local screen only. Evaluation corrections change search bounds and tree shape; no Elo claim."
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("source_sha256", "positions")}), flush=True)


if __name__ == "__main__":
    main()
