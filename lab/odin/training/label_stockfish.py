"""Label a frozen Odin corpus with offline Stockfish; never submission code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import chess
import chess.engine


ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "lab" / "odin" / "training"
DEFAULT_ENGINE = Path(
    r"stockfish"
)


def key(row: dict[str, object]) -> str:
    return f"{row['source_game']}:{row['ply']}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=TRAINING / "corpus-20k.jsonl")
    parser.add_argument("--output", type=Path, default=TRAINING / "labels-sf19-n2000.jsonl")
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--nodes", type=int, default=2_000)
    parser.add_argument("--limit", type=int, help="temporary prefix for smoke testing")
    args = parser.parse_args()
    if args.nodes <= 0:
        raise SystemExit("--nodes must be positive")
    if not args.engine.is_file():
        raise SystemExit(f"Stockfish binary missing: {args.engine}")
    rows = [json.loads(line) for line in args.corpus.read_text(encoding="utf-8").splitlines()]
    if args.limit is not None:
        rows = rows[:args.limit]
    done: set[str] = set()
    if args.output.exists():
        done = {key(json.loads(line)) for line in args.output.read_text(encoding="utf-8").splitlines() if line}
    todo = [row for row in rows if key(row) not in done]
    began = time.perf_counter()
    labelled = 0
    excluded_mates = 0
    engine = chess.engine.SimpleEngine.popen_uci(str(args.engine))
    try:
        engine.configure({"Threads": 1, "Hash": 16})
        with args.output.open("a", encoding="utf-8") as out:
            for row in todo:
                board = chess.Board(str(row["fen"]))
                info = engine.analyse(board, chess.engine.Limit(nodes=args.nodes))
                score = info["score"].pov(chess.WHITE)
                if score.is_mate():
                    excluded_mates += 1
                    continue
                labelled_row = dict(row)
                labelled_row["sf19_white_cp"] = score.score()
                labelled_row["sf_nodes"] = int(info.get("nodes", 0))
                labelled_row["sf_depth"] = int(info.get("depth", 0))
                out.write(json.dumps(labelled_row, separators=(",", ":")) + "\n")
                labelled += 1
                if labelled % 100 == 0:
                    out.flush()
                if labelled and labelled % 500 == 0:
                    elapsed = time.perf_counter() - began
                    print(json.dumps({"new_labels": labelled, "remaining": len(todo) - labelled,
                                      "elapsed_s": round(elapsed, 1)}), flush=True)
    finally:
        engine.quit()
    print("ODIN LABEL PASS " + json.dumps({
        "new_labels": labelled, "previous_labels": len(done), "excluded_mates": excluded_mates,
        "nodes": args.nodes, "elapsed_s": round(time.perf_counter() - began, 2),
    }), flush=True)


if __name__ == "__main__":
    main()
