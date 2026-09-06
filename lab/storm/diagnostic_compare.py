"""Lab-only, equal-budget probes of previously recorded difficult positions.

The two R12 preferences come from the platform review cited in V3_VALIDATION.
They are historical review labels, not new ground truth. Other roots are
unlabelled: a different move is a diagnostic observation, not a solved puzzle.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import inspect
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ("r12-before16-Nxd6", 12, 16, True, "Nxc5"),
    ("r12-before24-Rh3", 12, 24, True, "Rb3"),
    ("r13-before15-Bb7", 13, 15, False, None),
    ("r13-before17-hxg6", 13, 17, False, None),
    ("r13-before19-Ba6", 13, 19, False, None),
    ("r13-before26-Rxe1", 13, 26, False, None),
    ("r13-before31-Kg8", 13, 31, False, None),
    ("r04-before13-Qd8", 4, 13, False, None),
]


def pin_cpu(cpu):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    assert kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), 1 << cpu)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pin_cpu(args.cpu)
    sys.path.insert(0, str(args.engine.resolve()))
    import chess
    import chess.pgn
    import core_nb as c
    from board_nb import from_fen, move_uci
    from movegen_nb import generate_legal

    source_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(args.engine.glob("*.py"))
    }
    assert c.warmup() and c.NUMBA_READY
    print(args.name, "warmup", round(c.WARMUP_S, 3), flush=True)
    real_root = c.root_search_nb
    parameters = list(inspect.signature(real_root.py_func).parameters)
    idx = {name: parameters.index(name) for name in ("depth", "alpha", "beta", "nodes", "aborted")}
    trace = []

    def observed_root(*a):
        before = time.perf_counter()
        nodes_before = int(a[idx["nodes"]][0])
        move, score = real_root(*a)
        aborted = bool(a[idx["aborted"]][0])
        alpha, beta = int(a[idx["alpha"]]), int(a[idx["beta"]])
        trace.append({
            "depth": int(a[idx["depth"]]), "move": move_uci(int(move)),
            "score": int(score), "aborted": aborted,
            "accepted_iteration": not aborted and alpha < score < beta,
            "alpha": alpha, "beta": beta,
            "nodes": int(a[idx["nodes"]][0]) - nodes_before,
            "elapsed_ms": (time.perf_counter() - before) * 1000.0,
        })
        return move, score

    c.root_search_nb = observed_root  # Python wrapper only; compiled search is untouched.
    cases = []
    for case_id, round_number, fullmove, white_to_move, preferred_san in CASES:
        path = next((ROOT / "Chess_results_day1").glob(f"aichessathon-round-{round_number}-*.pgn"))
        with path.open(encoding="utf-8-sig") as stream:
            game = chess.pgn.read_game(stream)
        board = game.board()
        history = [from_fen(board.fen()).key]
        found = False
        actual_move = None
        for move in game.mainline_moves():
            if board.fullmove_number == fullmove and board.turn == white_to_move:
                found, actual_move = True, board.san(move)
                break
            board.push(move)
            history.append(from_fen(board.fen()).key)
        assert found, case_id
        preferred_uci = board.parse_san(preferred_san).uci() if preferred_san else None
        cases.append({
            "id": case_id, "fen": board.fen(), "game_history_keys": history,
            "actual_v1_move": actual_move, "review_preferred_san": preferred_san,
            "review_preferred_uci": preferred_uci,
            "label_status": "historical site review preference" if preferred_san else "unlabelled divergence diagnostic",
        })

    report = {
        "engine": args.name, "directory": str(args.engine.resolve()), "cpu": args.cpu,
        "source_sha256": source_hashes, "warmup_s": c.WARMUP_S, "results": [],
        "conditions": "Windows ARM/emulated x64 Python312, one pinned CPU; hard=soft allowance. TT, killers and heuristic history reset for every probe; PGN repetition history retained. Clock controllers may stop early and actual elapsed time is reported.",
        "labels": "Only R12 Nxc5/Rb3 are historical review preferences (Stockfish16 depth16, documented earlier). No new oracle analysis; other move changes are unlabelled.",
        "followup_policy": "9000ms only for R12 preferences not found at3000ms, plus the stubborn unlabelled R4 Qd8 diagnostic. It is not a proposed per-move clock allocation.",
    }

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def probe(case, budget_ms):
        for name in ("TT_KEY", "TT_MOVE", "TT_SCORE", "TT_DEPTH", "TT_GEN", "KILLERS", "HISTORY"):
            getattr(c, name).fill(0)
        c.TT_AGE[0] = 1
        trace.clear()
        pos = from_fen(case["fen"])
        packed = generate_legal(pos)
        before = time.perf_counter()
        chosen = c.search_root(pos, packed, float(budget_ms), float(budget_ms), False,
                               case["game_history_keys"])
        elapsed_ms = (time.perf_counter() - before) * 1000.0
        uci = move_uci(chosen)
        board = chess.Board(case["fen"])
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves
        accepted = [row for row in trace if row["accepted_iteration"]]
        final = accepted[-1] if accepted else {"depth": 0, "score": None}
        if accepted:
            assert final["move"] == uci, (final, uci)
        result = {k: v for k, v in case.items() if k != "game_history_keys"}
        result.update({
            "budget_ms": budget_ms, "elapsed_ms": elapsed_ms,
            "completed_depth": final["depth"], "score": final["score"],
            "nodes": int(c.last_nodes()), "move": uci, "san": board.san(move),
            "matches_review_preference": uci == case["review_preferred_uci"] if case["review_preferred_uci"] else None,
            "iterations": list(trace),
        })
        report["results"].append(result)
        print(args.name, case["id"], budget_ms, result["san"],
              "d", final["depth"], "cp", final["score"],
              "nodes", result["nodes"], "ms", round(elapsed_ms, 1), flush=True)
        save()
        return result

    initial = [probe(case, 3000) for case in cases]
    for case, result in zip(cases, initial):
        if (case["review_preferred_uci"] and not result["matches_review_preference"]) or case["id"] == "r04-before13-Qd8":
            probe(case, 9000)
    report["source_unchanged"] = source_hashes == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(args.engine.glob("*.py"))
    }
    save()
    assert report["source_unchanged"], "engine source changed during probe"


if __name__ == "__main__":
    main()
