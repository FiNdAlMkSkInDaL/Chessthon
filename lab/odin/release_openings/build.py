"""Freeze realistic, candidate-blind development and release openings.

This script never imports an agent. Public game prefixes are split before the
independent Stockfish balance screen; no candidate result influences selection.
"""
from __future__ import annotations

import argparse
import ctypes
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import chess
import chess.engine
import chess.pgn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TRAIN = ROOT / "lab/odin/training/corpus-20k.jsonl"
ENGINE = Path(r"stockfish")
SEED = "odin-release-openings-20260905-v1"
NODES = 200_000
QUOTAS = {"development": {"e4": 3, "d4": 3, "flank": 2},
          "holdout": {"e4": 16, "d4": 16, "flank": 8}}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bkey(board):
    return " ".join(board.fen(en_passant="legal").split()[:4])


def prefix_board(prefix):
    board = chess.Board()
    for move in prefix.split():
        board.push_uci(move)
    return bkey(board)


def metrics(board):
    developed = sum(1 for colour in chess.COLORS for p in (chess.KNIGHT, chess.BISHOP)
                    for sq in board.pieces(p, colour)
                    if chess.square_rank(sq) != (0 if colour else 7))
    castles = [("K" if chess.square_file(board.king(c)) >= 5 else "Q")
               if chess.square_rank(board.king(c)) == (0 if c else 7)
               and chess.square_file(board.king(c)) in (1, 2, 6) else "none"
               for c in (chess.WHITE, chess.BLACK)]
    material = sum((1 if c else -1) * w * len(board.pieces(p, c))
                   for c in chess.COLORS
                   for p, w in ((chess.PAWN, 1), (chess.KNIGHT, 3),
                                (chess.BISHOP, 3), (chess.ROOK, 5), (chess.QUEEN, 9)))
    locked_pairs = sum(1 for sq in board.pieces(chess.PAWN, chess.WHITE)
                       if chess.square_file(sq) in (2, 3, 4, 5) and sq + 8 < 64
                       and board.piece_at(sq + 8) == chess.Piece(chess.PAWN, chess.BLACK))
    return {"developed_minors": developed, "castles": castles,
            "king_placement": "opposite" if set(castles) == {"K", "Q"} else
                "same" if castles[0] == castles[1] != "none" else "one",
            "material_white": material, "locked_centre_pairs": locked_pairs,
            "piece_count": len(board.piece_map()), "in_check": board.is_check()}


def known_positions():
    result = set()
    files = []
    for pattern in ("Chess_results_day1/*.pgn", "chess_results_day2/*.pgn", "lab/storm/*.pgn"):
        for path in sorted(ROOT.glob(pattern)):
            files.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
            with path.open(encoding="utf-8-sig", errors="replace") as handle:
                while game := chess.pgn.read_game(handle):
                    board = game.board()
                    result.add(bkey(board))
                    for move in game.mainline_moves():
                        board.push(move)
                        result.add(bkey(board))
    old_fen = ROOT / "lab/openings.fen"
    if old_fen.exists():
        files.append({"path": str(old_fen.relative_to(ROOT)), "sha256": sha(old_fen)})
        for line in old_fen.read_text().splitlines():
            if line and not line.startswith("#"):
                result.add(bkey(chess.Board(line)))
    return result, files


def prepare():
    training_rows = [json.loads(line) for line in TRAIN.read_text().splitlines()]
    prefixes = {r["opening_key"] for r in training_rows}
    training_boards = {prefix_board(p) for p in prefixes}
    training_positions = {bkey(chess.Board(r["fen"])) for r in training_rows}
    known, known_files = known_positions()
    family_rows = {}
    counts = Counter()
    sources = []
    for path in sorted((HERE / "raw").glob("*.pgn")):
        sources.append({"file": path.name, "pgn_sha256": sha(path),
                        "zip_sha256": sha(path.with_suffix(".zip")),
                        "url": f"https://www.pgnmentor.com/players/{path.stem}.zip"})
        with path.open(encoding="utf-8-sig", errors="replace") as handle:
            index = 0
            while game := chess.pgn.read_game(handle):
                index += 1
                counts["games"] += 1
                if game.errors or game.board().fen() != chess.STARTING_FEN:
                    continue
                all_moves = list(game.mainline_moves())
                if len(all_moves) < 30:
                    continue
                # Prevent identical training games resurfacing through the opponent's file.
                prefix = " ".join(m.uci() for m in all_moves[:8])
                family = prefix_board(prefix)
                if prefix in prefixes or family in training_boards:
                    counts["known_training_prefix_games"] += 1
                    continue
                board = chess.Board()
                for ply, move in enumerate(all_moves[:20], start=1):
                    board.push(move)
                    if ply not in (16, 18, 20):
                        continue
                    key = bkey(board)
                    if key in known or key in training_positions or board.is_game_over(claim_draw=True):
                        continue
                    met = metrics(board)
                    if met["in_check"] or abs(met["material_white"]) > 1 or met["developed_minors"] < 4 or met["castles"] == ["none", "none"]:
                        continue
                    first = all_moves[0].uci()
                    group = "e4" if first == "e2e4" else "d4" if first == "d2d4" else "flank"
                    split = "development" if int(hashlib.sha256((SEED + family).encode()).hexdigest(), 16) % 5 == 0 else "holdout"
                    order = hashlib.sha256((SEED + path.name + str(index) + str(ply)).encode()).hexdigest()
                    row = {"id": order[:16], "split": split, "group": group, "fen": board.fen(),
                           "ply": ply, "opening_key": prefix, "opening_position_key": family,
                           "source_file": path.name, "source_game": index,
                           "headers": dict(game.headers), "prefix_uci": [m.uci() for m in all_moves[:ply]],
                           "geometry": met, "selection_order": order}
                    family_rows.setdefault(family, []).append(row)
    # One start per transposition-aware first-eight-ply family, selected solely by deterministic hash.
    rows = sorted((min(v, key=lambda r: r["selection_order"]) for v in family_rows.values()),
                  key=lambda r: r["selection_order"])
    # Family may transpose later; never let board placement repeat across partitions.
    unique = {}
    for row in rows:
        unique.setdefault(bkey(chess.Board(row["fen"])), row)
    rows = list(unique.values())
    (HERE / "candidate-pool.jsonl").write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8")
    prov = {"prepared_utc": datetime.now(timezone.utc).isoformat(), "seed": SEED,
            "quotas": QUOTAS, "source_files": sources, "training_corpus_sha256": sha(TRAIN),
            "excluded_training_prefixes": len(prefixes), "excluded_training_prefix_positions": len(training_boards),
            "known_position_count": len(known), "known_files": known_files,
            "pool_sha256": sha(HERE / "candidate-pool.jsonl"), "candidate_pool_count": len(rows),
            "counts": dict(counts), "pool_counts": dict(Counter(r["split"] + ":" + r["group"] for r in rows)),
            "selection": "Split hash first-eight-ply board key before independent analysis; one hash-chosen 16/18/20-ply start per family; no candidate engine queried. Reject all exact first-eight-ply training prefixes and their transpositions; reject all known game/diagnostic positions and training positions.",
            "screen": {"nodes": NODES, "max_abs_white_cp": 70, "threads": 1, "hash_mb": 32,
                       "clear_hash_each_position": True, "cpu": 4,
                       "selection_order": "Opposite-castled prefixes first, then fixed hash order within each split/group; minimum geometry requirements applied before screening.",
                       "exact_score": "Last exact completed iteration in streaming UCI info; report total nodes and exact-score nodes separately."},
            "limitations": "A first-eight-ply board key is narrower than an ECO family; established chess structures can resemble training despite exact-prefix/transposition disjointness. Public database collections overlap players but excluded opening prefixes prevent reused training games. The agent starts from FEN with empty game history as on the site."}
    (HERE / "provenance-pre-screen.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pool": len(rows), "counts": prov["pool_counts"]}), flush=True)


def screen():
    pool = [json.loads(line) for line in (HERE / "candidate-pool.jsonl").read_text().splitlines()]
    assert sha(HERE / "candidate-pool.jsonl") == json.loads((HERE / "provenance-pre-screen.json").read_text())["pool_sha256"]
    pool.sort(key=lambda r: (r["geometry"]["king_placement"] != "opposite", r["selection_order"]))
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    if not kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), 1 << 4):
        raise ctypes.WinError(ctypes.get_last_error())
    engine = chess.engine.SimpleEngine.popen_uci(str(ENGINE))
    engine.configure({"Threads": 1, "Hash": 32})
    selected, attempted = [], []
    counts = Counter()
    started = time.monotonic()
    try:
        for row in pool:
            split, group = row["split"], row["group"]
            if counts[(split, group)] >= QUOTAS[split][group]:
                continue
            engine.configure({"Clear Hash": None})
            board = chess.Board(row["fen"])
            exact = None
            total_nodes = 0
            with engine.analysis(board, chess.engine.Limit(nodes=NODES), game=object()) as analysis:
                for update in analysis:
                    total_nodes = max(total_nodes, update.get("nodes", 0))
                    if "score" in update and not update.get("lowerbound") and not update.get("upperbound"):
                        exact = update
            assert exact is not None
            info = exact
            score = info["score"].white()
            measured = dict(row)
            measured["reference"] = {"white_cp": score.score(), "mate": score.mate(),
                "nodes": total_nodes, "exact_score_nodes": info.get("nodes"), "depth": info.get("depth"), "pv": [m.uci() for m in info.get("pv", [])],
                "time_s": info.get("time"), "lowerbound": info.get("lowerbound", False), "upperbound": info.get("upperbound", False)}
            accepted = not score.is_mate() and abs(score.score()) <= 70 and total_nodes >= NODES
            measured["accepted"] = accepted
            attempted.append(measured)
            if accepted:
                selected.append(measured)
                counts[(split, group)] += 1
            print(json.dumps({"screened": len(attempted), "selected": len(selected), "elapsed_s": round(time.monotonic() - started, 1)}), flush=True)
            if len(selected) == 48:
                break
    finally:
        engine.quit()
    (HERE / "independent-screen.jsonl").write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in attempted), encoding="utf-8")
    assert len(selected) == 48, counts
    for split in QUOTAS:
        rows = [r for r in selected if r["split"] == split]
        for index, row in enumerate(rows):
            row["opening_index"] = index
        (HERE / f"{split}.jsonl").write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8")
        (HERE / f"{split}.fen").write_text("".join(r["fen"] + "\n" for r in rows), encoding="utf-8")
    holdout = [r for r in selected if r["split"] == "holdout"]
    guard = []
    for group, amount in (("e4", 6), ("d4", 6), ("flank", 4)):
        guard.extend([r["opening_index"] for r in holdout if r["group"] == group][:amount])
    guard.sort()
    report = {"frozen_utc": datetime.now(timezone.utc).isoformat(),
              "engine": {"name": "Stockfish 19", "path": str(ENGINE), "sha256": sha(ENGINE),
                         "purpose": "Offline independent starting-position balance only; never submission code."},
              "screen_nodes": NODES, "screened": len(attempted), "selected": len(selected),
              "counts": {s: dict(Counter(r["group"] for r in selected if r["split"] == s)) for s in QUOTAS},
              "geometry": {s: dict(Counter(r["geometry"]["king_placement"] for r in selected if r["split"] == s)) for s in QUOTAS},
              "guard_holdout_indices": guard,
              "files": {p.name: sha(p) for p in HERE.glob("*.jsonl")},
              "fen_files": {p.name: sha(p) for p in HERE.glob("*.fen")},
              "pre_screen_sha256": sha(HERE / "provenance-pre-screen.json"),
              "independence": "No candidate or control engine was imported or played during construction. Final positions remain excluded from development tuning. Guard reuses predeclared holdout subset and is reported separately."}
    (HERE / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("OPENINGS FROZEN " + json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "screen"))
    args = parser.parse_args()
    (prepare if args.stage == "prepare" else screen)()
