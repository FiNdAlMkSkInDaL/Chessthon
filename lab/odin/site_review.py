"""Replay and audit the ten supplied Storm platform games; never imports an engine.

Run with the repository's Python 3.12 / python-chess environment.
Telemetry S4.p starts at our first served root, which may follow an opening
opponent move; PGN game_ply is one-based and unambiguous.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import statistics

import chess
import chess.pgn

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "lab/odin/site_review.json"
VALUES = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300,
          chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
SELECTED = {
    16: {"30.Qd1": "Reference suggests serious positional deterioration despite eventual win",
         "47.Kh2": "Winning side must respect opponent d2 passer", "54.g6+": "Positive control: mating attack"},
    17: {"18...b6": "Queenside space and open-file concession", "23...Bxe4": "Minor-piece exchange and rook invasion",
         "38...e6": "Central break immediately precedes d6/d7 passer",
         "59...Bf8": "Reference finds quiet queen defense and near-equality", "64...Be7": "Queen-bishop ending before c5 break",
         "66...Kg7": "e6 pawn and king coordination before tactical collapse"},
    18: {"19.Bxc6": "Bishop-knight exchange and structural tradeoff", "21.Qd1": "Reference suggests Bd2 preserves equality",
         "28.Re1": "Equal material before positional deterioration",
         "30.Qd2": "Recapture structure before Bxf3", "39.Qg4": "Restricted pieces despite equal material",
         "42.Qd3": "Before loss of d4 pawn", "45.Qb1": "Before d4 break and c-pawn conversion"},
    19: {"21.Qb3": "Positive control: mate proof should terminate search early"},
    20: {"38...f5": "Reference prefers immediate e4 breakthrough", "43...e3": "Positive control: passed pawn with king attack"},
    21: {"41...Nf4": "Positive control: attack and queenside passer", "46...b2": "Positive control: conversion by passed pawn"},
    22: {"27.Qd2": "Reference identifies central counterplay e5", "28.Rcd1": "Exchange sacrifice and dynamic compensation",
         "32.Qxf4": "Material gain against advanced a-pawn", "35.Qd2": "Reference finds drawing Bxg6 attack",
         "47.Rg3": "Rooks versus rook-bishop and dangerous passers", "63.Rd1": "Defending second-rank passers",
         "72.Rh8": "Reference finds Rxh2 drawing resource", "73.Rc8+": "Three second-rank passers: never equate material with winning",
         "80.Ra3+": "Preserve defensive perpetual"},
    23: {"24.Ne2": "Middlegame maneuver before kingside expansion", "27.Ng3": "Before knight exchange opens f-file/pawn shelter",
         "28.Qe2": "Reference prefers Nf1 before structural damage",
         "30.h4": "Pawn-shelter and file-opening tradeoff", "32.Bf2": "Before Ne4/Rh6 attack",
         "33.Rc2": "Before Rh6", "34.Qf3": "King-danger recognition; root clock still 49s",
         "35.Qe2": "After g4, before Qf5", "36.Qd3": "Internal score collapses after Qf5"},
    24: {"48.b5": "Positive control: initiating a queenside passer", "55.b6": "Positive control: passed pawn with knight activity",
         "60.b7": "Positive control: promotion conversion"},
    25: {"26...f5": "Positive control: central/kingside break despite long think",
         "34...Kg6": "Do not turn king-safety terms into blanket king-walk prohibitions"},
}


def mat(board, color):
    return sum(len(board.pieces(pt, color)) * value for pt, value in VALUES.items())


def pawns(board, color):
    ours = board.pieces(chess.PAWN, color)
    theirs = board.pieces(chess.PAWN, not color)
    passed = []
    isolated = []
    for square in ours:
        file, rank = chess.square_file(square), chess.square_rank(square)
        if not any(abs(chess.square_file(other) - file) == 1 for other in ours):
            isolated.append(chess.square_name(square))
        if not any(abs(chess.square_file(other) - file) <= 1 and
                   (chess.square_rank(other) > rank if color else chess.square_rank(other) < rank)
                   for other in theirs):
            passed.append(chess.square_name(square))
    return {"passed": passed, "isolated": isolated,
            "doubled_extra": sum(max(0, sum(chess.square_file(s) == f for s in ours) - 1)
                                  for f in range(8))}


def review(path):
    raw = path.read_bytes()
    logpath = path.with_suffix(".log")
    logbytes = logpath.read_bytes()
    log = logbytes.decode("utf-8-sig")
    with path.open(encoding="utf-8-sig") as stream:
        game = chess.pgn.read_game(stream)
    assert not game.errors, (path, game.errors)
    team = re.search(r"^  Team\s+(.+)$", log, re.M).group(1).strip()
    own_color = chess.WHITE if game.headers["White"] == team else chess.BLACK
    assert game.headers["White" if own_color else "Black"] == team
    assert (re.search(r"^  Colour\s+(.+)$", log, re.M).group(1).strip() == "White") == own_color
    telemetry = {}
    for p, d, n, s, t, b in re.findall(r"S4 p(\d+) d(\d+) n(\d+) s(-?\d+) t(\d+) b(\d+)", log):
        p = int(p)
        assert p not in telemetry
        telemetry[p] = {"p": p, "depth": int(d), "nodes": int(n), "score_cp": int(s),
                        "search_ms": int(t), "final_soft_target_ms": int(b)}
    board = game.board()
    first_own_offset = 0 if board.turn == own_color else 1
    clocks = {chess.WHITE: 120.0, chess.BLACK: 120.0}
    decisions = {chess.WHITE: 0, chess.BLACK: 0}
    rows = []
    for game_ply, node in enumerate(game.mainline(), 1):
        assert board.outcome(claim_draw=True) is None, (path, game_ply, "played after outcome")
        move = node.move
        assert move in board.legal_moves, (path, game_ply, "illegal")
        actor = board.turn
        decisions[actor] += 1
        after_clock = node.clock()
        assert after_clock is not None
        before_clock = clocks[actor]
        elapsed = before_clock + .5 - after_clock
        assert elapsed >= -.001, (path, game_ply, elapsed)
        clocks[actor] = after_clock
        tel = telemetry.get(game_ply - 1 - first_own_offset) if actor == own_color else None
        row = {"game_ply": game_ply, "fen_before": board.fen(),
               "label": str(board.fullmove_number) + ("." if actor else "...") + board.san(move),
               "uci": move.uci(), "side": "white" if actor else "black", "own": actor == own_color,
               "decision": decisions[actor], "clock_before_s": before_clock,
               "clock_after_s": after_clock, "elapsed_s": round(elapsed, 6),
               "in_check_before": board.is_check(), "legal_moves": board.legal_moves.count(),
               "capture": board.is_capture(move), "promotion": move.promotion,
               "own_material_cp_before": mat(board, own_color) - mat(board, not own_color),
               "own_pawns_before": pawns(board, own_color),
               "opponent_pawns_before": pawns(board, not own_color),
               "telemetry": tel,
               "pgn_eval": str(node.eval()) if node.eval() is not None else None}
        board.push(move)
        row.update(fen_after=board.fen(), gives_check=board.is_check(),
                   own_material_cp_after=mat(board, own_color) - mat(board, not own_color))
        rows.append(row)
    terminal = board.outcome(claim_draw=True)
    assert terminal and terminal.result() == game.headers["Result"], (path, terminal)
    ours = [row for row in rows if row["own"]]
    theirs = [row for row in rows if not row["own"]]
    assert len(telemetry) == sum(row["telemetry"] is not None for row in ours)
    prospective_repetitions = []
    if board.can_claim_threefold_repetition():
        for move in list(board.legal_moves):
            label = board.san(move)
            board.push(move)
            if board.is_repetition(3):
                prospective_repetitions.append({"uci": move.uci(), "san": label})
            board.pop()
    def side_summary(side_rows):
        return {"moves": len(side_rows), "total_thinking_s": round(sum(r["elapsed_s"] for r in side_rows), 6),
                "remaining_s": side_rows[-1]["clock_after_s"],
                "first20_s": round(sum(r["elapsed_s"] for r in side_rows[:20]), 6),
                "first20_complete": len(side_rows) >= 20,
                "max_move_s": max(r["elapsed_s"] for r in side_rows),
                "max_move": max(side_rows, key=lambda r:r["elapsed_s"])["label"],
                "forced_moves": [{"label": r["label"], "game_ply": r["game_ply"],
                                   "elapsed_s": r["elapsed_s"]} for r in side_rows if r["legal_moves"] == 1],
                "mean_seconds_by_own_decision_bin": {
                    label: statistics.mean(values) if values else None
                    for label, values in ((f"{lo}-{hi}", [r["elapsed_s"] for r in side_rows if lo <= r["decision"] <= hi])
                                          for lo, hi in [(1,20),(21,40),(41,60),(61,1000)])}}
    own_telemetry = [r for r in ours if r["telemetry"]]
    score_drops = sorted([
        {"before": prior["label"], "after": current["label"], "game_ply": current["game_ply"],
         "change_cp": current["telemetry"]["score_cp"] - prior["telemetry"]["score_cp"],
         "from_cp": prior["telemetry"]["score_cp"], "to_cp": current["telemetry"]["score_cp"]}
        for prior, current in zip(own_telemetry, own_telemetry[1:])
        if abs(prior["telemetry"]["score_cp"]) < 30000 and abs(current["telemetry"]["score_cp"]) < 30000
    ], key=lambda r:r["change_cp"])[:8]
    return {"round": int(game.headers["Round"]), "source_pgn": str(path.relative_to(ROOT)),
            "source_pgn_sha256": hashlib.sha256(raw).hexdigest(),
            "source_log_sha256": hashlib.sha256(logbytes).hexdigest(), "headers": dict(game.headers),
            "team": team, "own_color": "white" if own_color else "black",
            "opponent": game.headers["Black" if own_color else "White"],
            "opening": re.search(r"^  Opening\s+(.+)$", log, re.M).group(1).strip(),
            "init_s_rounded_log": float(re.search(r"Ready in\s+([\d.]+) s", log).group(1)),
            "result_own": "draw" if terminal.winner is None else "win" if terminal.winner == own_color else "loss",
            "plies": len(rows), "opening_plies_implied_fen": (game.board().fullmove_number - 1) * 2 + (not game.board().turn),
            "final_fen": board.fen(), "terminal": terminal.termination.name,
            "terminal_without_claim": board.outcome(claim_draw=False).termination.name if board.outcome(claim_draw=False) else None,
            "terminal_current_threefold": board.is_repetition(3),
            "terminal_claiming_next_moves": prospective_repetitions,
            "own": side_summary(ours), "opponent_clock": side_summary(theirs),
            "telemetry_records": len(telemetry), "first_own_pgn_offset": first_own_offset,
            "largest_internal_score_drops": score_drops,
            "first_internal_mate_proof": next(({"label": r["label"], "game_ply": r["game_ply"],
                                                "score_cp": r["telemetry"]["score_cp"],
                                                "clock_after_s":r["clock_after_s"]}
                                               for r in ours if r["telemetry"] and r["telemetry"]["score_cp"] > 30000), None),
            "moves": rows}


def main():
    games = [review(path) for path in sorted((ROOT / "chess_results_day2").glob("*.pgn"))]
    assert [g["round"] for g in games] == list(range(16,26))
    ours = [row for game in games for row in game["moves"] if row["own"]]
    losses = [g for g in games if g["result_own"] == "loss"]
    summary = {"wins": sum(g["result_own"] == "win" for g in games),
               "draws": sum(g["result_own"] == "draw" for g in games),
               "losses": len(losses), "total_plies": sum(g["plies"] for g in games),
               "own_moves": len(ours), "telemetry_records": sum(g["telemetry_records"] for g in games),
               "mean_own_remaining_s": statistics.mean(g["own"]["remaining_s"] for g in games),
               "mean_losses_own_remaining_s": statistics.mean(g["own"]["remaining_s"] for g in losses),
               "mean_own_remaining_excluding_short_R19_s": statistics.mean(g["own"]["remaining_s"] for g in games if g["round"] != 19),
               "mean_own_thinking_s": statistics.mean(g["own"]["total_thinking_s"] for g in games),
               "mean_opponent_remaining_s": statistics.mean(g["opponent_clock"]["remaining_s"] for g in games),
               "first20_complete_mean_s": statistics.mean(g["own"]["first20_s"] for g in games if g["own"]["first20_complete"]),
               "first20_complete_sd_s": statistics.pstdev(g["own"]["first20_s"] for g in games if g["own"]["first20_complete"]),
               "max_move_s": max(r["elapsed_s"] for r in ours),
               "max_init_s_rounded_log": max(g["init_s_rounded_log"] for g in games),
               "forced_moves": sum(r["legal_moves"] == 1 for r in ours),
               "forced_seconds": sum(r["elapsed_s"] for r in ours if r["legal_moves"] == 1),
               "mean_seconds_by_own_decision_bin": {
                   f"{lo}-{hi}": statistics.mean(r["elapsed_s"] for r in ours if lo <= r["decision"] <= hi)
                   for lo, hi in [(1,20),(21,40),(41,60),(61,1000)]}}
    selected = []
    for game in games:
        for row in game["moves"]:
            reason = SELECTED.get(game["round"], {}).get(row["label"])
            if reason:
                selected.append({"round": game["round"], "reason": reason, **row})
    assert len(selected) == sum(len(labels) for labels in SELECTED.values())
    result = {"description": "Legal and chronological replay of all ten supplied Storm day-two site PGNs and S4 logs.",
              "runtime_chess_version": chess.__version__, "telemetry_score_perspective": "Storm; not independent ground truth",
              "pgn_game_ply_convention": "one-based move index from supplied starting FEN",
              "clock_model": "120s initial plus 0.5s after each move; PGN clock precision 1ms",
              "summary": summary, "selected_diagnostic_roots": selected, "games": games}
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for g in games:
        print(g["round"], g["result_own"], g["plies"], g["own"]["remaining_s"], g["own"]["first20_s"],
              g["terminal"], g["terminal_claiming_next_moves"])


if __name__ == "__main__":
    main()
