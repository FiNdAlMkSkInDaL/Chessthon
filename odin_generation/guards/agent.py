"""Submission entrypoint. The platform does `import agent` and calls get_move."""

from __future__ import annotations

import time
import sys

import chess

import history
from board_nb import from_fen, move_uci
from eval_nb import evaluate
from search_nb import iterative_deepening, packed_for_uci, tt_move_if_legal
from storm_clock import allocation, phase_units

# Odin generation guards. Storm-derived selective search with original offline-fitted
# positional evaluation, legal SEE/EP and current 600-ply referee handling.
# The historical S4 stderr tag is retained for telemetry parser compatibility.
# The current live init allowance is 90 s; the signer keeps a 55 s target.

try:
    import core_nb

    core_nb.warmup()
except Exception:
    pass


def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal UCI move. Colour is the side to move in fen."""
    started_at = time.perf_counter()
    try:
        board = chess.Board(fen)
    except ValueError:
        board = chess.Board()
    legal = list(board.legal_moves)
    if not legal:
        # Unreachable under the live referee (outcome() before get_move).
        return "0000"
    fallback = legal[0].uci()
    try:
        return _search_move(board, time_left_ms, legal, fallback, started_at)
    except Exception:
        return fallback


def _search_move(
    board: chess.Board,
    time_left_ms: int,
    legal: list[chess.Move],
    fallback: str,
    started_at: float | None = None,
) -> str:
    if started_at is None:
        started_at = time.perf_counter()
    history.observe_served(board)
    fen = board.fen(en_passant="fen")
    pos = from_fen(fen)
    winning = history.is_winning(
        evaluate(pos, adjudicate=history.use_adjudication_eval()),
        adjudicate=history.use_adjudication_eval(),
    )
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    draw_scan_ms = min(50.0, max(0.0, float(time_left_ms) - elapsed_ms - 600.0))
    filtered = history.filter_root_moves(
        board,
        legal,
        winning,
        deadline=time.perf_counter() + draw_scan_ms / 1000.0,
    )
    legal_uci = {m.uci() for m in legal}
    chosen = filtered[0].uci()
    try:
        packed = packed_for_uci(pos, [m.uci() for m in filtered])
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        effective_time_ms = max(0, int(float(time_left_ms) - elapsed_ms))
        mode, soft_ms, hard_ms = allocation(
            effective_time_ms, history.game_ply(), phase=phase_units(pos.bb),
            root_moves=len(filtered), in_check=board.is_check(),
        )
        if len(filtered) == 1:
            chosen = filtered[0].uci()
        elif mode == "panic":
            tm = tt_move_if_legal(packed, pos.key) if packed else 0
            if tm:
                chosen = move_uci(tm)
        elif packed:
            best = iterative_deepening(
                pos,
                packed,
                hard_ms=hard_ms,
                soft_ms=soft_ms,
                adjudicate=history.use_adjudication_eval(),
                game_zkeys=history.zkeys(),
            )
            chosen = move_uci(best)
            if core_nb.NUMBA_READY:
                info = core_nb.last_info()
                print(f"S4 p{history.game_ply()} d{info.get('depth', 0)} "
                      f"n{info.get('nodes', 0)} s{info.get('score', 0)} "
                      f"t{int(info.get('elapsed_ms', 0))} "
                      f"b{int(info.get('target_ms', 0))}", file=sys.stderr)
        if chosen not in legal_uci:
            chosen = filtered[0].uci() if filtered else legal[0].uci()
    finally:
        try:
            history.observe_our_uci(board, chosen)
        except Exception:
            pass
    return chosen
