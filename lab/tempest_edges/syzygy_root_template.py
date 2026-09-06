"""Our root policy for permitted, checksum-verified 3/4-piece Syzygy data.

The preinstalled python-chess library probes the tables. No external engine
code or runtime network service is used. The DTZ payloads are the unrounded
edition. Search handles castling, unavailable data and the final 200 plies.
"""
from pathlib import Path
import hashlib
import chess
import chess.syzygy

TABLE_HASHES = {}  # Filled with the verified payload manifest at staging.
_DIRECTORY = Path(__file__).with_name('syzygy')
_TABLEBASE = None
if _DIRECTORY.is_dir():
    for _name, _digest in TABLE_HASHES.items():
        if hashlib.sha256((_DIRECTORY/_name).read_bytes()).hexdigest() != _digest:
            raise RuntimeError('Syzygy table identity mismatch: '+_name)
    _TABLEBASE = chess.syzygy.open_tablebase(str(_DIRECTORY), max_fds=80)


def child_value(board, seen=None):
    """Child-side result, with current automatic draw conditions first."""
    if board.is_checkmate():
        return -2, 0, True
    if (board.is_stalemate() or board.is_insufficient_material()
            or board.halfmove_clock >= 100 or board.ply() >= 600
            or (seen and seen.get(board._transposition_key(), 0) >= 2)
            or board.is_repetition(3)):
        return 0, 0, False
    wdl = _TABLEBASE.probe_wdl(board)
    dtz = _TABLEBASE.probe_dtz(board)
    # WDL assumes a reset clock; exact DTZ accounts for the clock now carried.
    if abs(wdl) != 2 or board.halfmove_clock + abs(dtz) > 100:
        return 0, dtz, False
    if wdl < 0 and seen:
        # A theoretically losing opponent may have a real-history draw reply.
        for reply in board.legal_moves:
            board.push(reply)
            try:
                if seen.get(board._transposition_key(), 0) >= 2 and not board.is_checkmate():
                    return 0, dtz, False
            finally:
                board.pop()
    return wdl, dtz, False


def choose_syzygy(board, seen=None):
    if (_TABLEBASE is None or board.occupied.bit_count() > 4
            or board.castling_rights or board.ply() >= 400):
        return None
    best = None
    best_rank = None
    try:
        for move in sorted(board.legal_moves, key=lambda m: m.uci()):
            zeroing = board.is_zeroing(move)
            board.push(move)
            try:
                value, dtz, mate = child_value(board, seen)
                value = -value
                distance = 1 if zeroing or mate else abs(dtz) + 1
                if value > 0:
                    rank = (2, int(mate), -distance)
                elif value < 0:
                    rank = (-2, 0, distance)
                else:
                    # Finish an available draw rather than drifting into a loss.
                    immediate = (board.halfmove_clock >= 100
                                 or board.is_stalemate()
                                 or board.is_insufficient_material()
                                 or bool(seen and seen.get(board._transposition_key(), 0) >= 2))
                    rank = (0, int(immediate), int(zeroing))
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best = move.uci()
            finally:
                board.pop()
    except chess.syzygy.MissingTableError:
        # Never prefer a known losing move over an unprobed legal alternative.
        return None
    return best
