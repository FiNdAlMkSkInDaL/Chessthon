"""ID + fail-soft AB + qsearch + TT + ordering.

Numba path (core_nb) also has PVS, RFP, NMP, IIR, check extension. No LMR.
Python fallback stays plain AB — only used if Numba warmup fails.
"""

from __future__ import annotations

import time

from board_nb import (
    make,
    move_from,
    move_is_capture,
    move_is_ep,
    move_promo,
    move_to,
    move_uci,
    unmake,
)
from eval_nb import evaluate, insufficient_material
from movegen_nb import (
    bishop_attacks,
    generate_legal,
    generate_noisy,
    in_check,
    rook_attacks,
)
from tables_nb import KING_ATK, KNIGHT_ATK, PAWN_ATK, WHITE, lsb
from time_nb import MIN_ITER_MS
from tt_nb import EXACT, LOWER, UPPER, tt

MATE = 32_000
INF = 32_001
MAX_DEPTH = 64
MAX_PLY = 96
DRAW = 0
ASPIRATION = 25
DELTA = 200
SEE_VAL = (100, 300, 300, 500, 900, 20_000)
STALEMATE_SCAN_MAX_PIECES = 8

_aborted = False
_deadline = 0.0
_allow_abort = False
_nodes = 0
_adjudicate = False
_killers = [[0, 0] for _ in range(MAX_PLY)]
_history = [[0] * 64 for _ in range(12)]


class SearchAborted(Exception):
    pass


def _check_clock() -> None:
    global _aborted
    if not _allow_abort:
        return
    if time.perf_counter() >= _deadline:
        _aborted = True
        raise SearchAborted


def _is_repeat(key: int, hist: list[int]) -> bool:
    # A second occurrence is not an automatic draw.  The referee claims only
    # on a current third occurrence or an intended legal move to one.
    return hist.count(key) >= 2


def _has_repetition_pair(hist: list[int], current: int) -> bool:
    seen: set[int] = set()
    for key in hist + [current]:
        if key in seen:
            return True
        seen.add(key)
    return False


def _threefold_claim_from_legal(pos, hist: list[int], legal: list[int]) -> bool:
    prior = hist + [pos.key]
    for move in legal:
        undo = make(pos, move)
        try:
            if prior.count(pos.key) >= 2:
                return True
        finally:
            unmake(pos, move, undo)
    return False


def _cap_terminal(pos, ply: int) -> int:
    legal = generate_legal(pos)
    if not legal and in_check(pos, pos.side):
        return -MATE + ply
    return DRAW


def _is_zeroing(pos, move: int) -> bool:
    mover = pos.mb[move_from(move)]
    return move_is_capture(move) or (mover >= 0 and mover % 6 == 0)


def _fifty_claim_from_legal(pos, legal: list[int]) -> bool:
    if pos.fifty >= 100:
        return True
    for move in legal:
        if _is_zeroing(pos, move):
            continue
        undo = make(pos, move)
        try:
            continues = bool(generate_legal(pos))
        finally:
            unmake(pos, move, undo)
        if continues:
            return True
    return False


def _gives_check(pos, move: int) -> bool:
    undo = make(pos, move)
    try:
        return in_check(pos, pos.side)
    finally:
        unmake(pos, move, undo)


def _victim_pt(pos, move: int) -> int:
    if move_is_ep(move):
        return 0
    cap = pos.mb[move_to(move)]
    return cap % 6 if cap >= 0 else 0


def _lva(pos, to: int, side: int, occ: int) -> int:
    base = 0 if side == WHITE else 6
    bb = PAWN_ATK[side ^ 1][to] & pos.bb[base] & occ
    if bb:
        return lsb(bb)
    bb = KNIGHT_ATK[to] & pos.bb[base + 1] & occ
    if bb:
        return lsb(bb)
    bish_q = bishop_attacks(to, occ) & occ
    bb = bish_q & pos.bb[base + 2]
    if bb:
        return lsb(bb)
    rook_q = rook_attacks(to, occ) & occ
    bb = rook_q & pos.bb[base + 3]
    if bb:
        return lsb(bb)
    bb = (bish_q | rook_q) & pos.bb[base + 4]
    if bb:
        return lsb(bb)
    bb = KING_ATK[to] & pos.bb[base + 5] & occ
    if bb:
        return lsb(bb)
    return -1


def see(pos, move: int) -> int:
    """Legality-aware fallback swap-off. Positive favours the mover.

    This path is used only when native warmup fails, so clarity is preferable
    to duplicating the old geometric shortcut.  The compiled path has its own
    bounded native implementation; neither one invents pinned or illegal king
    recaptures.
    """
    frm = move_from(move)
    to = move_to(move)
    mover = pos.mb[frm]
    if mover < 0:
        return 0
    promo = move_promo(move)
    if move_is_ep(move):
        gain = SEE_VAL[0]
    else:
        cap = pos.mb[to]
        gain = SEE_VAL[cap % 6] if cap >= 0 else 0
    if promo:
        gain += SEE_VAL[promo] - SEE_VAL[0]
    trial = pos.copy()
    make(trial, move)
    hanging = SEE_VAL[trial.mb[to] % 6]
    gains = [gain]
    while True:
        captures = [
            candidate
            for candidate in generate_legal(trial)
            if move_to(candidate) == to
            and (move_is_capture(candidate) or move_is_ep(candidate))
        ]
        if not captures:
            break
        capture = min(captures, key=lambda candidate: trial.mb[move_from(candidate)] % 6)
        promoted = move_promo(capture)
        bonus = SEE_VAL[promoted] - SEE_VAL[0] if promoted else 0
        gains.append(hanging + bonus - gains[-1])
        make(trial, capture)
        hanging = SEE_VAL[trial.mb[to] % 6]
        if hanging == SEE_VAL[5]:
            break
    i = len(gains) - 1
    while i > 0:
        gains[i - 1] = -max(-gains[i - 1], gains[i])
        i -= 1
    return gains[0]


def _order(pos, moves: list[int], ply: int, hash_move: int) -> list[int]:
    if len(moves) <= 1:
        return moves
    k0 = k1 = 0
    if ply < MAX_PLY:
        k0, k1 = _killers[ply][0], _killers[ply][1]

    def key(m: int) -> tuple:
        if hash_move and m == hash_move:
            return (0, 0)
        if move_is_capture(m) or move_promo(m):
            att = pos.mb[move_from(m)]
            return (1, -(_victim_pt(pos, m) * 16 - (att % 6 if att >= 0 else 0)))
        if m == k0:
            return (2, 0)
        if m == k1:
            return (3, 0)
        p = pos.mb[move_from(m)]
        return (4, -_history[p][move_to(m)] if p >= 0 else 0)

    return sorted(moves, key=key)


def _cutoff_quiet(pos, move: int, depth: int, ply: int) -> None:
    if move_is_capture(move) or move_promo(move) or ply >= MAX_PLY:
        return
    if _killers[ply][0] != move:
        _killers[ply][1] = _killers[ply][0]
        _killers[ply][0] = move
    p = pos.mb[move_from(move)]
    if p < 0:
        return
    h = _history[p][move_to(move)] + depth * depth
    _history[p][move_to(move)] = 10_000 if h > 10_000 else h


def _qsearch(pos, alpha: int, beta: int, ply: int, hist: list[int], cap_left: int) -> int:
    global _nodes
    _nodes += 1
    _check_clock()
    if ply >= MAX_PLY:
        return evaluate(pos, adjudicate=_adjudicate)
    if cap_left <= 0:
        return _cap_terminal(pos, ply)

    checked = in_check(pos, pos.side)
    legal_at_fifty: list[int] | None = None
    repeated = _is_repeat(pos.key, hist)
    pair = _has_repetition_pair(hist, pos.key)
    if repeated or pos.fifty >= 99 or pair:
        if pos.fifty >= 99 or checked or repeated or pair:
            legal_at_fifty = generate_legal(pos)
            if not legal_at_fifty:
                return -MATE + ply if checked else DRAW
        if repeated:
            return DRAW
        if _fifty_claim_from_legal(pos, legal_at_fifty):
            return DRAW
        if pair and _threefold_claim_from_legal(pos, hist, legal_at_fifty):
            return DRAW
    if insufficient_material(pos):
        return DRAW
    orig_alpha = alpha
    hash_move = 0
    if not _adjudicate:
        hit = tt.probe(pos.key)
        if hit is not None:
            move, _d, flag, raw = hit
            hash_move = move
            s = tt.score_at(raw, ply)
            if flag == EXACT:
                return s
            if flag == LOWER and s >= beta:
                return s
            if flag == UPPER and s <= alpha:
                return s

    if not checked:
        stand = evaluate(pos, adjudicate=_adjudicate)
        if stand >= beta:
            if pos.occ.bit_count() <= STALEMATE_SCAN_MAX_PIECES and not generate_legal(pos):
                return DRAW
            if not _adjudicate:
                tt.store(pos.key, 0, 0, LOWER, stand, ply)
            return stand
        if stand > alpha:
            alpha = stand
        moves = generate_noisy(pos)
        if (
            not moves
            and pos.occ.bit_count() <= STALEMATE_SCAN_MAX_PIECES
            and not generate_legal(pos)
        ):
            return DRAW
        best = stand
    else:
        stand = 0
        moves = legal_at_fifty if legal_at_fifty is not None else generate_legal(pos)
        if not moves:
            return -MATE + ply
        best = -INF

    best_move = 0
    hist.append(pos.key)
    try:
        for move in _order(pos, moves, ply, hash_move):
            if not checked:
                promo = move_promo(move)
                cap_v = SEE_VAL[_victim_pt(pos, move)]
                if promo:
                    cap_v += SEE_VAL[promo] - SEE_VAL[0]
                delta_bad = stand + cap_v + DELTA < alpha
                see_bad = move != hash_move and see(pos, move) < 0
                if (delta_bad or see_bad) and not _gives_check(pos, move):
                    continue
            undo = make(pos, move)
            try:
                score = -_qsearch(pos, -beta, -alpha, ply + 1, hist, cap_left - 1)
            finally:
                unmake(pos, move, undo)
            if score > best:
                best = score
                best_move = move
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
    finally:
        hist.pop()

    if not _adjudicate:
        flag = EXACT
        if best <= orig_alpha:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        tt.store(pos.key, best_move, 0, flag, best, ply)
    return best


def _negamax(
    pos, depth: int, alpha: int, beta: int, ply: int, hist: list[int], cap_left: int
) -> int:
    global _nodes
    _nodes += 1
    _check_clock()

    if ply >= MAX_PLY:
        return evaluate(pos, adjudicate=_adjudicate)
    if cap_left <= 0:
        return _cap_terminal(pos, ply)

    checked = in_check(pos, pos.side)
    legal_at_fifty: list[int] | None = None
    repeated = _is_repeat(pos.key, hist)
    pair = _has_repetition_pair(hist, pos.key)
    if repeated or pos.fifty >= 99 or pair:
        if pos.fifty >= 99 or checked or repeated or pair:
            legal_at_fifty = generate_legal(pos)
            if not legal_at_fifty:
                return -MATE + ply if checked else DRAW
        if repeated:
            return DRAW
        if _fifty_claim_from_legal(pos, legal_at_fifty):
            return DRAW
        if pair and _threefold_claim_from_legal(pos, hist, legal_at_fifty):
            return DRAW
    if insufficient_material(pos):
        return DRAW
    if depth <= 0:
        return _qsearch(pos, alpha, beta, ply, hist, cap_left)

    orig_alpha = alpha
    hash_move = 0
    if not _adjudicate:
        hit = tt.probe(pos.key)
        if hit is not None:
            move, tdepth, flag, raw = hit
            hash_move = move
            if tdepth >= depth:
                s = tt.score_at(raw, ply)
                if flag == EXACT:
                    return s
                if flag == LOWER and s >= beta:
                    return s
                if flag == UPPER and s <= alpha:
                    return s

    moves = legal_at_fifty if legal_at_fifty is not None else generate_legal(pos)
    if not moves:
        if checked:
            return -MATE + ply
        return DRAW

    hist.append(pos.key)
    best = -INF
    best_move = 0
    try:
        for move in _order(pos, moves, ply, hash_move):
            undo = make(pos, move)
            try:
                score = -_negamax(pos, depth - 1, -beta, -alpha, ply + 1, hist, cap_left - 1)
            finally:
                unmake(pos, move, undo)
            if score > best:
                best = score
                best_move = move
            if best > alpha:
                alpha = best
            if alpha >= beta:
                _cutoff_quiet(pos, move, depth, ply)
                break
    finally:
        hist.pop()

    if not _adjudicate:
        flag = EXACT
        if best <= orig_alpha:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        tt.store(pos.key, best_move, depth, flag, best, ply)
    return best


def _root_search(
    pos,
    moves: list[int],
    depth: int,
    hist: list[int],
    pv: int | None,
    alpha: int,
    beta: int,
    cap_left: int,
) -> tuple[int, int]:
    global _allow_abort
    ordered = _order(pos, moves, 0, pv or 0)
    best_move = ordered[0]
    best_score = -INF
    hist.append(pos.key)
    try:
        for move in ordered:
            _allow_abort = True
            undo = make(pos, move)
            try:
                score = -_negamax(pos, depth - 1, -beta, -alpha, 1, hist, cap_left - 1)
            finally:
                unmake(pos, move, undo)
            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
    finally:
        hist.pop()
        _allow_abort = True
    return best_move, best_score


def iterative_deepening(
    pos,
    packed_root: list[int],
    *,
    hard_ms: float,
    soft_ms: float,
    adjudicate: bool = False,
    game_zkeys: list[int] | None = None,
    absolute_ply: int = 0,
) -> int:
    global _aborted, _deadline, _allow_abort, _nodes, _adjudicate
    if not packed_root:
        raise ValueError("no root moves")
    import core_nb
    if core_nb.HAS_NUMBA and core_nb.NUMBA_READY:
        # Do not restart another search with a fresh budget after an error.
        # The root firewall already has a legal fallback.
        return core_nb.search_root(
            pos, packed_root, hard_ms, soft_ms, game_zkeys or [], absolute_ply
        )
    # Kept as a compatibility argument for old diagnostics. The live referee
    # draws at its cap; it never asks us for material adjudication.
    # Disables position-only fallback TT cutoffs.  Native search stores scores
    # under a complete rule/history context; a rare fallback must not revive
    # the old unsafe identity merely to save a few nodes.
    _adjudicate = True
    _aborted = False
    _nodes = 0
    for ply in range(MAX_PLY):
        _killers[ply][0] = _killers[ply][1] = 0
    start = time.perf_counter()
    _deadline = start + hard_ms / 1000.0
    best = packed_root[0]
    prev = 0
    hist_base = list(game_zkeys[:-1] if game_zkeys else [])
    cap_left = max(0, 600 - int(absolute_ply))

    for depth in range(1, MAX_DEPTH + 1):
        now = time.perf_counter()
        elapsed_ms = (now - start) * 1000.0
        remaining_ms = hard_ms - elapsed_ms
        # Keep the legal root fallback rather than starting an unabortable
        # depth-one qsearch with too little time remaining.
        if remaining_ms < MIN_ITER_MS:
            break
        if depth > 1 and elapsed_ms >= soft_ms:
            break
        _allow_abort = False
        window = (-INF, INF) if depth <= 1 else (prev - ASPIRATION, prev + ASPIRATION)
        try:
            move, score = _root_search(
                pos, packed_root, depth, hist_base, best, window[0], window[1], cap_left
            )
            if depth > 1 and (score <= window[0] or score >= window[1]):
                move, score = _root_search(
                    pos, packed_root, depth, hist_base, best, -INF, INF, cap_left
                )
            best = move
            prev = score
        except SearchAborted:
            break
        if _aborted:
            break
    return best


def packed_for_uci(pos, uci_moves: list[str]) -> list[int]:
    by_uci = {move_uci(m): m for m in generate_legal(pos)}
    return [by_uci[u] for u in uci_moves if u in by_uci]


def tt_move_if_legal(packed_root: list[int], key: int) -> int:
    try:
        import core_nb

        if core_nb.NUMBA_READY:
            move = core_nb.probe_move(key)
            return move if move in packed_root else 0
    except Exception:
        pass
    hit = tt.probe(key)
    if hit is None:
        return 0
    move = hit[0]
    return move if move in packed_root else 0


def qsearch_score(pos) -> int:
    global _allow_abort, _adjudicate
    _allow_abort = False
    _adjudicate = True
    return _qsearch(pos, -INF, INF, 0, [], 600)
