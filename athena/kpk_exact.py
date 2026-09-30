"""Original KPK mate distance with exact fifty-move counter, root policy only."""
from pathlib import Path
import hashlib
import chess
import numpy as np
from endgame_exact import distance as major_distance

_PATH = Path(__file__).with_name('kpk_dtm.npz')
_SHA256 = 'e9ca64056081c99f8078439671b1ca88f5f2270498d3754383092443daa74a8b'
if hashlib.sha256(_PATH.read_bytes()).hexdigest() != _SHA256:
    raise RuntimeError('KPK table identity mismatch')
with np.load(_PATH, allow_pickle=False) as data:
    _raw = data['dtm']
    if _raw.dtype != np.uint8 or _raw.shape != (24, 100, 8192):
        raise RuntimeError('KPK table shape mismatch')
    # A bytes-backed view cannot be made writable again by toggling flags.
    _DTM = np.frombuffer(_raw.tobytes(), dtype=np.uint8).reshape(24, 100, 8192)
    del _raw

def distance(board, attacker):
    pawns = board.pieces(chess.PAWN, attacker)
    if len(pawns) != 1 or board.halfmove_clock >= 100:
        return None
    p = next(iter(pawns))
    ak, dk = board.king(attacker), board.king(not attacker)
    if not attacker:
        p, ak, dk = p ^ 56, ak ^ 56, dk ^ 56
    if p % 8 > 3:
        p, ak, dk = p ^ 7, ak ^ 7, dk ^ 7
    pi = (p // 8 - 1) * 4 + p % 8
    idx = int(board.turn != attacker) * 4096 + ak * 64 + dk
    d = int(_DTM[pi, board.halfmove_clock, idx])
    return None if d == 255 else d

def choose_kpk(board, seen=None):
    if (board.occupied.bit_count() != 3 or board.pawns.bit_count() != 1
            or board.kings.bit_count() != 2 or board.castling_rights
            or board.ep_square is not None or not board.is_valid()):
        return None
    attacker = board.color_at(chess.lsb(board.pawns))
    mover = board.turn
    best, best_rank = None, None
    for move in sorted(board.legal_moves, key=lambda m: m.uci()):
        board.push(move)
        try:
            if board.is_checkmate():
                won, d = True, 0
            elif (board.halfmove_clock >= 100 or board.ply() >= 600
                  or board.is_stalemate() or board.is_insufficient_material()
                  or (seen and seen.get(board._transposition_key(), 0) >= 2)):
                won, d = False, None
            else:
                if board.pawns:
                    d = distance(board, attacker)
                elif board.queens or board.rooks:
                    kind = chess.QUEEN if board.queens else chess.ROOK
                    d = major_distance(board, attacker, kind)
                    if d is not None and d > 100 - board.halfmove_clock:
                        d = None
                else:
                    d = None
                won = d is not None and d <= 600 - board.ply()
            if won:
                rank = (1, -d) if mover == attacker else (-1, d)
            else:
                rank = (0, 0)
            if best_rank is None or rank > best_rank:
                best, best_rank = move.uci(), rank
        finally:
            board.pop()
    return best
