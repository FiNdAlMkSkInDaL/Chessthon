"""Reconstruct and audit final opening files without an agent import."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import chess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def key(board):
    return " ".join(board.fen(en_passant="legal").split()[:4])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "manifest.json").read_text())
    for filename, expected in {**manifest["files"], **manifest["fen_files"]}.items():
        assert digest(HERE / filename) == expected, filename
    training = [json.loads(line) for line in (ROOT / "lab/odin/training/corpus-20k.jsonl").read_text().splitlines()]
    training_prefixes = {r["opening_key"] for r in training}
    training_keys = set()
    for prefix in training_prefixes:
        board = chess.Board()
        for move in prefix.split():
            board.push_uci(move)
        training_keys.add(key(board))
    rows = []
    reports = {}
    for split, count in (("development", 8), ("holdout", 40)):
        chosen = [json.loads(line) for line in (HERE / f"{split}.jsonl").read_text().splitlines()]
        fens = (HERE / f"{split}.fen").read_text().splitlines()
        assert len(chosen) == len(fens) == count
        assert [r["opening_index"] for r in chosen] == list(range(count))
        for row, fen in zip(chosen, fens):
            board = chess.Board()
            for ply, uci in enumerate(row["prefix_uci"], 1):
                board.push_uci(uci)
                if ply == 8:
                    assert key(board) == row["opening_position_key"]
                    assert key(board) not in training_keys
            assert board.fen() == fen == row["fen"]
            assert row["opening_key"] not in training_prefixes
            assert board.is_valid() and not board.is_check() and not board.is_game_over(claim_draw=True)
            assert 16 <= board.ply() <= 20
            assert row["reference"]["nodes"] >= 200_000
            assert row["reference"]["mate"] is None and abs(row["reference"]["white_cp"]) <= 70
            assert not row["reference"]["lowerbound"] and not row["reference"]["upperbound"]
        reports[split] = {"positions": count, "group_counts": dict(Counter(r["group"] for r in chosen)),
                          "eco_counts": dict(sorted(Counter(r["headers"].get("ECO", "unknown") for r in chosen).items())),
                          "mean_developed_minors": sum(r["geometry"]["developed_minors"] for r in chosen) / count,
                          "minimum_developed_minors": min(r["geometry"]["developed_minors"] for r in chosen),
                          "castling": dict(Counter(r["geometry"]["king_placement"] for r in chosen)),
                          "with_locked_central_pawns": sum(r["geometry"]["locked_centre_pairs"] > 0 for r in chosen),
                          "score_range_white_cp": [min(r["reference"]["white_cp"] for r in chosen), max(r["reference"]["white_cp"] for r in chosen)]}
        rows.extend(chosen)
    assert len({r["opening_position_key"] for r in rows}) == 48
    assert len({key(chess.Board(r["fen"])) for r in rows}) == 48
    guard = manifest["guard_holdout_indices"]
    assert len(guard) == len(set(guard)) == 16 and set(guard).issubset(range(40))
    result = {"status": "PASS", "checks": "48 legal independently screened prefixes; immutable file hashes; 48 distinct first-eight-ply board families and starts; no prefix/transposition overlap with training; separate dev and final families; 16 predeclared guard subset indices.", "reports": reports, "guard_indices": guard}
    (HERE / "audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
