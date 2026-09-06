"""Submission entrypoint. The platform does `import agent` and calls get_move."""

from __future__ import annotations

import chess

import history
import tb_nb
from board_nb import from_fen, move_uci
from eval_nb import evaluate
from search_nb import iterative_deepening, packed_for_uci, tt_move_if_legal
from time_nb import allocation

# Import runs once per game inside the platform's 90 s budget, before the
# clock starts. The signer retains a much stricter ~55 s release target.
# Brick C: ID + AB + qsearch + TT + ordering. Panic: TT move if legal, else first legal. No qsearch in panic.
# Numba: PVS + RFP + NMP + IIR + SEE + improving + dynamic ID clock.
# LMR: ENABLE_LMR in core_nb (False until SPRT H1 vs last-good).
# Root 3-piece Syzygy if syzygy/*.rtbw exist; draw-seek + late clock in history/time.
# Warmup on Linux 3.12; abort if compile exceeds ~50 s.

try:
    import core_nb

    core_nb.warmup()
except Exception:
    pass


def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal UCI move. Colour is the side to move in fen."""
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
        return _search_move(board, time_left_ms, legal, fallback)
    except Exception:
        return fallback


def _search_move(
    board: chess.Board,
    time_left_ms: int,
    legal: list[chess.Move],
    fallback: str,
) -> str:
    history.observe_served(board)
    fen = board.fen(en_passant="fen")
    pos = from_fen(fen)
    adj = history.use_adjudication_eval()
    score = evaluate(pos, adjudicate=adj)
    winning = history.is_winning(score, adjudicate=adj)
    losing = history.is_losing(score, adjudicate=adj)
    filtered = history.filter_root_moves(board, legal, winning, losing)
    if not filtered:
        filtered = legal
    legal_uci = {m.uci() for m in legal}
    chosen = filtered[0].uci()
    try:
        tb_choice = tb_nb.root_uci(board, filtered)
        if tb_choice is not None and tb_choice in legal_uci:
            chosen = tb_choice
            return chosen
        mode, soft_ms, hard_ms = allocation(int(time_left_ms), history.game_ply())
        packed = packed_for_uci(pos, [m.uci() for m in filtered])
        if mode == "panic":
            tm = tt_move_if_legal(packed, pos.key) if packed else 0
            if tm:
                chosen = move_uci(tm)
        elif packed:
            best = iterative_deepening(
                pos,
                packed,
                hard_ms=hard_ms,
                soft_ms=soft_ms,
                adjudicate=adj,
                game_zkeys=history.zkeys(),
            )
            chosen = move_uci(best)
        if chosen not in legal_uci:
            chosen = filtered[0].uci()
    except Exception:
        chosen = filtered[0].uci()
    finally:
        try:
            history.observe_our_uci(board, chosen)
        except Exception:
            pass
    return chosen
