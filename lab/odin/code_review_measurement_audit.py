"""Read-only validation of reference-review snapshots; no engine execution."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import chess
import chess.pgn

ROOT = Path(__file__).resolve().parents[2]


def corpus():
    out = {}
    for p in sorted((ROOT / "chess_results_day2").glob("*.pgn")):
        with p.open(encoding="utf-8-sig") as f:
            game = chess.pgn.read_game(f)
        assert not game.errors
        assert (game.headers["White"] == "Finlay Phillips") != (game.headers["Black"] == "Finlay Phillips")
        out[f'site-r{int(game.headers["Round"])}'] = (game, game.headers["White"] == "Finlay Phillips", p)
    for lane in "ab":
        p = ROOT / f"lab/storm/holdout-r2-lane-{lane}.jsonl"
        for line in p.read_text().splitlines():
            row = json.loads(line)
            if row.get("type") == "game":
                game = chess.pgn.read_game(io.StringIO(row["pgn"]))
                assert not game.errors
                assert row["candidate_colour"] in ("white", "black")
                out[f'holdout-{lane}-g{row["game"]}-o{row["opening_index"]}'] = (game, row["candidate_colour"] == "white", p)
    return out


def audit(path, games):
    raw = path.read_bytes()
    lines = raw.splitlines()
    partial_last_line = False
    parsed = []
    for i, line in enumerate(lines):
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            if i != len(lines)-1:
                raise
            partial_last_line = True
    meta = parsed[0]
    rows = [r for r in parsed if r["type"] == "position"]
    seen = set()
    counts = Counter()
    better_forced = []
    node_ratios = []
    pv_referee_terminals = []
    restricted_root_mismatches = []
    source_hashes = {}
    board_cache = {}
    for r in rows:
        gid, ply = r["game_id"], r["ply"]
        assert (gid, ply) not in seen
        seen.add((gid, ply))
        game, colour, source = games[gid]
        if source not in source_hashes:
            source_hashes[source] = hashlib.sha256(source.read_bytes()).hexdigest()
        assert r["source_sha256"] == source_hashes[source]
        assert r["storm_colour"] == ("white" if colour else "black")
        moves = list(game.mainline_moves())
        assert r["history_uci"] == [m.uci() for m in moves[:ply]]
        if gid not in board_cache:
            board_cache[gid] = (0, game.board())
        previous_ply, board = board_cache[gid]
        assert game.board().fen() == r["start_fen"]
        assert ply >= previous_ply
        for m in moves[previous_ply:ply]:
            assert m in board.legal_moves
            board.push(m)
        board_cache[gid] = (ply, board)
        assert board.fen() == r["fen"]
        assert r["storm_turn"] == (board.turn == colour)
        assert r["played_uci"] == (moves[ply].uci() if ply < len(moves) else None)
        result = board.outcome(claim_draw=True)
        if r.get("terminal"):
            assert result and result.termination.name == r["terminal"]
        else:
            assert result is None
        analyses = [("best", r), ("played", r.get("played_root"))]
        analyses += list(r.get("alternatives", {}).items())
        for kind, a in analyses:
            if not a:
                continue
            n = meta["deep_nodes"] if meta["mode"] == "deep" else (meta["site_nodes"] if gid.startswith("site") else meta["holdout_nodes"])
            if not a.get("terminal"):
                node_ratios.append(a["nodes"] / n)
            b = board.copy()
            for pi, uci in enumerate(a["pv_uci"]):
                m = chess.Move.from_uci(uci)
                assert m in b.legal_moves
                if pi == 0 and kind != "best":
                    expected = r["played_uci"] if kind == "played" else kind
                    if uci != expected:
                        restricted_root_mismatches.append({"game_id":gid,"ply":ply,"kind":kind,
                                                           "expected":expected,"actual":uci})
                outcome = b.outcome(claim_draw=True) if meta["mode"] == "deep" else None
                if outcome:
                    pv_referee_terminals.append({"game_id":gid, "ply":ply, "kind":kind,
                                                  "pv_index":pi, "terminal":outcome.termination.name,
                                                  "white_cp":a["white_cp"]})
                    break
                b.push(m)
        played = r.get("played_root")
        if played and r.get("white_mate") is None and played.get("white_mate") is None:
            sign = 1 if board.turn else -1
            gap = sign * (r["white_cp"] - played["white_cp"])
            if gap < 0:
                better_forced.append({"game_id":gid,"ply":ply,"best_cp":r["white_cp"],
                                      "forced_cp":played["white_cp"],"mover_gap":gap,
                                      "unrestricted_pv":r["pv_uci"][:1],"played":r["played_uci"]})
        counts[gid] += 1
    return {"path":str(path.relative_to(ROOT)),"snapshot_sha256":hashlib.sha256(raw).hexdigest(),
            "snapshot_bytes":len(raw),"positions":len(rows),"games":len(counts),
            "complete_summary":next((r for r in parsed if r["type"]=="summary"),None),
            "partial_last_line_ignored":partial_last_line,"counts":dict(counts),
            "actual_node_ratio_min":min(node_ratios),"actual_node_ratio_max":max(node_ratios),
            "forced_move_scored_better_than_unrestricted":better_forced,
            "restricted_root_mismatches":restricted_root_mismatches,
            "pvs_continuing_past_referee_claim":pv_referee_terminals,
            "result":"Source, colour, history, board, played move and legal PV replay pass; restricted-root mismatches, when present, invalidate those specific restricted analyses. Numeric reference scores are not certified."}


def main():
    games = corpus()
    report = {"checked_utc":datetime.now(timezone.utc).isoformat(),
              "checks":[audit(ROOT / "lab/odin/reference-screen.jsonl",games),
                        audit(ROOT / "lab/odin/reference-deep.jsonl",games)],
              "limitations":["Reference helper drops UCI lowerbound/upperbound flags.",
                             "python-chess analyse returns aggregated info, not one atomic last-score event.",
                             "Forced-root and unrestricted fixed-node searches distribute effort differently.",
                             "Stockfish's internal optional draw/cap model is not the exact competition referee.",
                             "SF WDL is its model estimate, not this tournament's win probability."]}
    (ROOT / "lab/odin/code_review_measurement_audit.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
