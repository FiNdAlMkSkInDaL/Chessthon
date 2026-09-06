"""Export replay-verified match PGNs with clocks and per-move evidence CSV.

This is a presentation/export helper, not a strength or release gate. It keeps
the immutable JSONL source paths and archive hashes in the exported headers.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import chess.pgn


def export(paths: list[Path], prefix: Path) -> int:
    starts = {}
    games = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("type") == "run_start":
                starts[row["run_id"]] = row
            elif row.get("type") == "game":
                games.append((path, row))
    games.sort(key=lambda item: (item[1]["opening_index"], item[1]["candidate_colour"] != "white"))
    pgns = []
    moves = []
    for path, row in games:
        start = starts[row["run_id"]]
        game = chess.pgn.read_game(io.StringIO(row["pgn"]))
        if game is None or game.errors:
            raise ValueError(f"Invalid PGN: {path}, game {row['game']}")
        game.headers["Event"] = "Storm v4 (revision r2) versus v3 native validation"
        game.headers["Site"] = "Local Linux validation"
        game.headers["Date"] = str(row["ts"])[:10].replace("-", ".")
        game.headers["Round"] = f"{row['opening_index']}.{1 if row['candidate_colour']=='white' else 2}"
        game.headers["White"] = "Storm v4" if row["white_role"] == "candidate" else "v3"
        game.headers["Black"] = "Storm v4" if row["black_role"] == "candidate" else "v3"
        game.headers["StormSHA256"] = row["candidate_sha256"]
        game.headers["V3SHA256"] = row["baseline_sha256"]
        game.headers["Evidence"] = f"{path.name}; {row['run_id']}; game {row['game']}"
        board = game.board()
        indices = {"white": 0, "black": 0}
        telemetry = {
            colour: {t["game_ply"]: t for t in row[colour + "_timing"].get("s4_telemetry", [])}
            for colour in indices
        }
        for ply, node in enumerate(game.mainline()):
            colour = "white" if board.turn else "black"
            index = indices[colour]
            observed = row[colour + "_timing"]["moves"][index]
            if not observed["ok"] or observed["move"] != node.move.uci():
                raise ValueError(f"PGN/move log mismatch: {path}, game {row['game']}, ply {ply}")
            if chess.Board(observed["fen"]).fen() != board.fen():
                raise ValueError(f"PGN/FEN mismatch: {path}, game {row['game']}, ply {ply}")
            after = (observed["time_left_ms"] - observed["elapsed_ms"] + start["increment_ms"]) / 1000
            node.set_clock(max(0.0, after))
            node.set_emt(observed["elapsed_ms"] / 1000)
            info = telemetry[colour].get(index * 2, {})
            moves.append({
                "run_id": row["run_id"], "opening_index": row["opening_index"],
                "candidate_colour": row["candidate_colour"], "game_ply": ply,
                "mover": game.headers[colour.capitalize()], "san": board.san(node.move),
                "uci": node.move.uci(), "time_before_s": observed["time_left_ms"] / 1000,
                "thinking_s": observed["elapsed_ms"] / 1000, "clock_after_s": after,
                "completed_depth": info.get("depth", ""),
                "search_nodes": info.get("nodes", ""),
                "score_from_mover_cp": info.get("score", ""),
                "search_target_ms": info.get("target_ms", ""),
            })
            indices[colour] += 1
            board.push(node.move)
        if any(indices[c] != len(row[c + "_timing"]["moves"]) for c in indices):
            raise ValueError(f"Unrepresented move request: {path}, game {row['game']}")
        pgns.append(game.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=True)))
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix(".pgn").write_text("\n\n".join(pgns) + "\n", encoding="utf-8")
    if moves:
        with prefix.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(moves[0]))
            writer.writeheader()
            writer.writerows(moves)
    return len(games)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    print(f"Exported {export(args.logs, args.prefix)} replay-verified games.")
