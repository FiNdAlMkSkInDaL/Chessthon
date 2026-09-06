"""Structural gate for Odin's known diagnostics, never a move-answer oracle."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import chess


ROOT = Path(__file__).resolve().parents[2]
ODIN = ROOT / "odin"
sys.path.insert(0, str(ODIN))

import history  # noqa: E402
from board_nb import from_fen  # noqa: E402
from movegen_nb import generate_legal, move_uci  # noqa: E402


def main() -> None:
    path = ROOT / "lab" / "odin" / "odin-diagnostics.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    metadata, cases = rows[0], rows[1:]
    assert metadata["type"] == "metadata"
    assert metadata["cases"] == 39
    assert len(cases) == 39

    reconstructed = 0
    all_roots = 0
    tablebase_roots = 0
    for case in cases:
        if case["kind"] == "exact_legal_exchange_fixture":
            board = chess.Board(case["fen"])
            assert chess.Move.from_uci(case["move_uci"]) in board.legal_moves
            continue
        board = chess.Board(case["start_fen"])
        for uci in case["history_uci"]:
            board.push_uci(uci)
        assert board.fen() == case["fen"]
        assert board.outcome(claim_draw=True) is None

        history.reset()
        replay = chess.Board(case["start_fen"])
        history.observe_served(replay)
        for uci in case["history_uci"]:
            replay.push_uci(uci)
            history.observe_served(replay)
        pos = from_fen(board.fen(en_passant="fen"))
        packed = generate_legal(pos)
        legal = list(board.legal_moves)
        returned = history.filter_root_moves(board, legal, winning=False)
        assert {m.uci() for m in returned} == {m.uci() for m in legal}
        assert {move_uci(m) for m in packed} == {m.uci() for m in legal}
        all_roots += len(legal)
        reconstructed += 1
        if "tablebase" in case:
            drawing = set(case["tablebase"]["drawing_moves"])
            assert drawing <= {m.uci() for m in returned}
            assert drawing <= {move_uci(m) for m in packed}
            tablebase_roots += 1

    print(
        "ODIN DIAGNOSTIC STRUCTURE PASS "
        + json.dumps({
            "game_roots": reconstructed,
            "legal_roots_checked": all_roots,
            "tablebase_roots": tablebase_roots,
            "note": "Checks legal reachability and no static root deletion; does not tune to expected moves.",
        }),
        flush=True,
    )


if __name__ == "__main__":
    main()
