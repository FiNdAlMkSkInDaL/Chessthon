"""Read-only Storm root-policy replay; no agent/core import or JIT."""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "storm"))
import chess
import chess.pgn
import history
from board_nb import from_fen
from eval_nb import evaluate


def scan(path, corpus):
    rows = []
    with path.open(encoding="utf-8-sig") as handle:
        gi = 0
        while (game := chess.pgn.read_game(handle)) is not None:
            gi += 1
            assert not game.errors
            names = [game.headers.get("White", ""), game.headers.get("Black", "")]
            color = next((c for c, name in zip([chess.WHITE, chess.BLACK], names)
                          if "Storm" in name or "Finlay Phillips" in name), None)
            if color is None:
                continue
            history.reset()
            board = game.board()
            root_ply = 0
            for node in game.mainline():
                move = node.move
                if board.turn == color:
                    history.observe_served(board)
                    legal = list(board.legal_moves)
                    pos = from_fen(board.fen(en_passant="fen"))
                    score = evaluate(pos, adjudicate=history.use_adjudication_eval())
                    winning = history.is_winning(score, adjudicate=history.use_adjudication_eval())
                    start = time.perf_counter()
                    filtered = history.filter_root_moves(board, legal, winning,
                                                         deadline=start + 0.050)
                    elapsed = (time.perf_counter() - start) * 1000
                    removed = [m for m in legal if m not in filtered]
                    if removed or board.halfmove_clock >= 85 or root_ply >= 275:
                        reasons = Counter()
                        for candidate in removed:
                            zeroing = board.is_zeroing(candidate)
                            board.push(candidate)
                            if board.is_checkmate():
                                reasons["mate_wrongly_removed"] += 1
                            elif board.is_stalemate() or board.is_insufficient_material():
                                reasons["immediate_draw"] += 1
                            elif winning and board.halfmove_clock and not zeroing and pos.fifty >= 90:
                                reasons["quiet_at_90"] += 1
                            elif winning and history._seen[board._transposition_key()] >= 1:
                                reasons["any_previous_occurrence"] += 1
                            else:
                                reasons["auto_claim_lookahead"] += 1
                            board.pop()
                        rows.append({"corpus": corpus, "path": str(path.relative_to(ROOT)),
                                     "game_index": gi, "headers": dict(game.headers),
                                     "played_ply": root_ply, "fullmove": board.fullmove_number,
                                     "turn": "white" if board.turn else "black", "fen": board.fen(),
                                     "halfmove": board.halfmove_clock, "pesto_score": score,
                                     "winning": winning, "legal_count": len(legal),
                                     "kept_count": len(filtered), "removed": [m.uci() for m in removed],
                                     "kept": [m.uci() for m in filtered], "played": move.uci(),
                                     "san": board.san(move), "reasons": dict(reasons),
                                     "scan_ms": elapsed})
                    history.observe_our_uci(board, move.uci())
                board.push(move)
                root_ply += 1
    return rows


def main():
    rows = []
    paths = sorted((ROOT / "chess_results_day2").glob("*.pgn"))
    for path in paths:
        rows += scan(path, "day2")
    match = ROOT / "lab/storm/Storm-v4-vs-v3-games.pgn"
    rows += scan(match, "native40")
    output = ROOT / "lab/odin/code_review_root_filter.json"
    result = {"description": "Storm root filter replay with actual game history and independent 50ms scan allowances; timing is local and not original game telemetry.",
              "source_hashes": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                for p in ["storm/history.py", "storm/core_nb.py", "storm/agent.py", "storm/storm_clock.py"]},
              "rows": rows}
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "removed": sum(bool(r["removed"]) for r in rows),
                      "forced": [{k:r[k] for k in ["corpus", "game_index", "headers", "fullmove", "turn", "fen", "pesto_score", "legal_count", "kept", "played", "reasons"]}
                                 for r in rows if r["kept_count"] == 1 or "quiet_at_90" in r["reasons"]]}, indent=2))


if __name__ == "__main__":
    main()
