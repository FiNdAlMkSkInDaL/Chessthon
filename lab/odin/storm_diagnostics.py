"""Cold-TT development probes of exact frozen Storm; never edits release code."""
from __future__ import annotations
import ctypes
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "lab/odin/storm_diagnostics.json"
CASES = [
    ("site-r17-before59-Bf8", 17, 59, False),
    ("site-r17-before64-Be7", 17, 64, False),
    ("site-r23-before28-Qe2", 23, 28, True),
    ("site-r23-before30-h4", 23, 30, True),
    ("site-r16-before24-Qe2", 16, 24, True),
    ("site-r18-before21-Qd1", 18, 21, True),
    ("native-165-before83-Rf4", None, 83, False),
]


def pin_cpu(cpu):
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    assert k.SetProcessAffinityMask(k.GetCurrentProcess(), 1 << cpu)


def source_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "storm").glob("*.py"))}


def main():
    pin_cpu(2)
    for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"]:
        os.environ[key] = "1"
    sys.path.insert(0, str(ROOT / "storm"))
    import chess
    import chess.pgn
    import core_nb as c
    import history as h
    from board_nb import from_fen, move_uci
    from eval_nb import evaluate
    from movegen_nb import generate_legal

    sources = source_hashes()
    manifest = json.loads((ROOT / "dist/storm-r2-linux-x86.manifest.json").read_text())
    expected = {r["name"]: r["sha256"] for r in manifest["entries"]}
    assert sources == expected, "Current Storm source is not exactly the frozen release"
    report = {"started_utc": datetime.now(timezone.utc).isoformat(),
              "archive_sha256": manifest["archive_sha256"], "source_sha256": sources,
              "python": sys.version, "platform": platform.platform(), "cpu": 2,
              "threads": 1, "results": [],
              "method": "Windows development diagnostic, exact frozen source, single pinned CPU, original native warmup. PGN positions replayed through original served/returned history APIs without prior searches. TT, killers and heuristic history reset for each root/budget. Both hard and initial soft allowances equal the stated budget; the unchanged controller may stop earlier. This is not original platform TT/heuristic state, not exact game reproduction, not a Linux speed or match measurement. Filter replay uses an independent 50ms allowance.",
              "intended_cases": CASES}

    def save():
        OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    assert c.warmup() and c.NUMBA_READY
    report["warmup_s"] = c.WARMUP_S
    report["numba_ready"] = c.NUMBA_READY
    print("warmup", round(c.WARMUP_S, 3), flush=True)
    save()

    real_root = c.root_search_nb
    parameters = list(inspect.signature(real_root.py_func).parameters)
    indexes = {key: parameters.index(key) for key in ["depth", "alpha", "beta", "nodes", "aborted"]}
    trace = []

    def observed_root(*args):
        before = time.perf_counter()
        before_nodes = int(args[indexes["nodes"]][0])
        move, score = real_root(*args)
        alpha, beta = int(args[indexes["alpha"]]), int(args[indexes["beta"]])
        aborted = bool(args[indexes["aborted"]][0])
        trace.append({"depth": int(args[indexes["depth"]]), "move": move_uci(int(move)),
                      "score": int(score), "alpha": alpha, "beta": beta,
                      "aborted": aborted, "exact_completed": not aborted and alpha < score < beta,
                      "bound": "aborted" if aborted else "upper" if score <= alpha else "lower" if score >= beta else "exact",
                      "nodes": int(args[indexes["nodes"]][0]) - before_nodes,
                      "elapsed_ms": 1000 * (time.perf_counter() - before)})
        return move, score

    c.root_search_nb = observed_root

    def get_case(case):
        cid, round_number, fullmove, colour = case
        if round_number is not None:
            p = next((ROOT / "chess_results_day2").glob(f"aichessathon-round-{round_number}-*.pgn"))
            with p.open(encoding="utf-8-sig") as f:
                game = chess.pgn.read_game(f)
        else:
            p = ROOT / "lab/storm/Storm-v4-vs-v3-games.pgn"
            with p.open(encoding="utf-8-sig") as f:
                while (game := chess.pgn.read_game(f)) is not None:
                    if game.headers["Round"] == "165.2":
                        break
            assert game is not None
        assert not game.errors
        board = game.board()
        h.reset()
        history_uci = []
        for played in game.mainline_moves():
            if board.turn == colour:
                h.observe_served(board)
                if board.fullmove_number == fullmove:
                    break
                h.observe_our_uci(board, played.uci())
            board.push(played)
            history_uci.append(played.uci())
        else:
            raise AssertionError(cid)
        assert board.turn == colour and board.fullmove_number == fullmove
        pos = from_fen(board.fen(en_passant="fen"))
        legal = list(board.legal_moves)
        static = evaluate(pos, adjudicate=h.use_adjudication_eval())
        winning = h.is_winning(static, adjudicate=h.use_adjudication_eval())
        t = time.perf_counter()
        filtered = h.filter_root_moves(board, legal, winning, deadline=t + .050)
        elapsed = 1000 * (time.perf_counter() - t)
        return {"id":cid, "source":str(p.relative_to(ROOT)),
                "source_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
                "fen":board.fen(), "start_fen":game.board().fen(), "history_uci":history_uci,
                "game_zkeys":h.zkeys().copy(), "game_ply":h.game_ply(),
                "actual_move":played.uci(), "actual_san":board.san(played),
                "static_score":static, "winning_flag":winning,
                "legal": [m.uci() for m in legal], "filtered":[m.uci() for m in filtered],
                "filter_ms":elapsed, "adjudicate":h.use_adjudication_eval()}

    cases = [get_case(case) for case in CASES]
    for case in cases:
        modes = ["filtered", "all_legal"] if case["id"].startswith("native") else ["filtered"]
        for mode in modes:
            for budget in [3000, 9000]:
                for key in ["TT_KEY", "TT_MOVE", "TT_SCORE", "TT_DEPTH", "TT_GEN", "KILLERS", "HISTORY"]:
                    getattr(c, key).fill(0)
                c.TT_AGE[0] = 1
                trace.clear()
                pos = from_fen(case["fen"])
                initial = (pos.bb.copy(), pos.mb.copy(), pos.key)
                allowed = set(case["filtered"] if mode == "filtered" else case["legal"])
                packed = [m for m in generate_legal(pos) if move_uci(m) in allowed]
                assert len(packed) == len(allowed)
                before = time.perf_counter()
                move = c.search_root(pos, packed, float(budget), float(budget),
                                     case["adjudicate"], case["game_zkeys"])
                elapsed = 1000 * (time.perf_counter() - before)
                assert (pos.bb, pos.mb, pos.key) == initial
                uci = move_uci(move)
                assert uci in allowed
                board = chess.Board(case["fen"])
                exact = [t for t in trace if t["exact_completed"]]
                if exact:
                    assert exact[-1]["move"] == uci
                info = c.last_info()
                result = {k:v for k,v in case.items() if k != "game_zkeys"}
                result.update({"root_mode":mode,"budget_ms":budget,"elapsed_ms":elapsed,
                               "move":uci,"san":board.san(chess.Move.from_uci(uci)),
                               "score":info["score"],"depth":info["depth"],
                               "nodes":c.last_nodes(),"aborted":info["aborted"],
                               "final_soft_target_ms":info["target_ms"],"iterations":trace.copy()})
                report["results"].append(result)
                save()
                print(case["id"], mode, budget, result["san"], "depth",result["depth"],
                      "score",result["score"],"ms",round(elapsed,1),flush=True)
    report["source_unchanged"] = sources == source_hashes()
    assert report["source_unchanged"]
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    save()


if __name__ == "__main__":
    main()
