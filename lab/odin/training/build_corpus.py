"""Build a deterministic, opening-family-split offline Odin fit corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random

import chess
import chess.pgn


ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "lab" / "odin" / "training" / "raw"
OUT = ROOT / "lab" / "odin" / "training"
SEED = 20260905
SOURCES = {
    "Carlsen": "https://www.pgnmentor.com/players/Carlsen.zip",
    "Kasparov": "https://www.pgnmentor.com/players/Kasparov.zip",
    "Anand": "https://www.pgnmentor.com/players/Anand.zip",
    "Karpov": "https://www.pgnmentor.com/players/Karpov.zip",
    "Tal": "https://www.pgnmentor.com/players/Tal.zip",
    "Fischer": "https://www.pgnmentor.com/players/Fischer.zip",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def opening_key(moves: list[str]) -> str:
    return " ".join(moves[:8]) or "start"


def split_for(opening: str) -> str:
    # An opening family never spans train/validation, even across games.
    value = int.from_bytes(hashlib.blake2b(opening.encode(), digest_size=8).digest(), "big")
    return "validation" if value % 5 == 0 else "train"


def bucket(board: chess.Board) -> str | None:
    phase = sum(len(board.pieces(piece, color)) * weight
                for color in (chess.WHITE, chess.BLACK)
                for piece, weight in ((chess.KNIGHT, 1), (chess.BISHOP, 1),
                                      (chess.ROOK, 2), (chess.QUEEN, 4)))
    ply = board.ply()
    if ply >= 36 and phase <= 8:
        return "ending"
    if ply >= 28 and phase >= 18:
        king_ranks = (chess.square_rank(board.king(chess.WHITE)), chess.square_rank(board.king(chess.BLACK)))
        if king_ranks[0] <= 1 or king_ranks[1] >= 6:
            return "attack"
    if ply >= 28 and phase >= 10:
        return "middlegame"
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--positions", type=int, default=20_000)
    args = parser.parse_args()
    assert args.positions >= 4
    quota = args.positions // 4
    candidates: dict[str, list[dict[str, object]]] = {key: [] for key in ("middlegame", "attack", "ending")}
    games = 0
    for pgn_path in sorted(RAW.glob("*.pgn")):
        with pgn_path.open(encoding="utf-8-sig", errors="replace") as handle:
            number = 0
            while game := chess.pgn.read_game(handle):
                number += 1
                games += 1
                board = game.board()
                uci_moves: list[str] = []
                selected_kinds: set[str] = set()
                for move in game.mainline_moves():
                    uci_moves.append(move.uci())
                    board.push(move)
                    kind = bucket(board)
                    # At most one deterministic position of each broad type
                    # per game.  This avoids a few long games dominating fit.
                    if kind is None or kind in selected_kinds or board.is_game_over(claim_draw=True):
                        continue
                    opening = opening_key(uci_moves)
                    candidates[kind].append({
                        "fen": board.fen(en_passant="fen"),
                        "source_game": f"{pgn_path.name}:{number}",
                        "opening_key": opening,
                        "split": split_for(opening),
                        "bucket": kind,
                        "ply": board.ply(),
                    })
                    selected_kinds.add(kind)
    rng = random.Random(SEED)
    selected: list[dict[str, object]] = []
    for kind, rows in candidates.items():
        rng.shuffle(rows)
        selected.extend(rows[:quota])
    # Fill a small rounding remainder while preserving determinism.
    selected_ids = {(str(row["source_game"]), int(row["ply"])) for row in selected}
    pool = [
        row for rows in candidates.values() for row in rows
        if (str(row["source_game"]), int(row["ply"])) not in selected_ids
    ]
    rng.shuffle(pool)
    selected.extend(pool[:args.positions - len(selected)])
    if len(selected) != args.positions:
        raise SystemExit(f"only found {len(selected)} usable positions")
    selected.sort(key=lambda row: (str(row["source_game"]), int(row["ply"])))
    corpus = OUT / "corpus-20k.jsonl"
    corpus.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in selected), encoding="utf-8")
    counts = {kind: sum(row["bucket"] == kind for row in selected) for kind in candidates}
    splits = {split: sum(row["split"] == split for row in selected) for split in ("train", "validation")}
    provenance = {
        "corpus": corpus.name, "seed": SEED, "positions": len(selected), "games_scanned": games,
        "bucket_counts": counts, "split_counts": splits,
        "split_rule": "Opening-key hash: no first-eight-ply opening family crosses train/validation.",
        "sources": {name: {"url": url, "pgn_sha256": digest(RAW / f"{name}.pgn")}
                    for name, url in SOURCES.items()},
        "exclusions": "Platform games, Odin diagnostics, prior reference roots and final match holdouts are not corpus inputs.",
    }
    (OUT / "corpus-20k.provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print("ODIN CORPUS PASS " + json.dumps({"positions": len(selected), "buckets": counts, "splits": splits}))


if __name__ == "__main__":
    main()
