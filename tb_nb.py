"""3-piece Syzygy at the root only.

5-piece WDL is ~378 MB (over the unzip cap). 3-piece WDL+DTZ is about a megabyte.
Search stays Numba; this uses python-chess on the already-filtered root list.
Missing tables are a no-op so a zip without syzygy/ still plays.
"""

from __future__ import annotations

from pathlib import Path

import chess
import chess.syzygy

MAX_PIECES = 3
_DIR = Path(__file__).resolve().parent / "syzygy"
_tb: chess.syzygy.Tablebase | None = None
_nfiles = -1


def load() -> int:
    """Open every *.rtbw/*.rtbz under syzygy/. Safe to call more than once."""
    global _tb, _nfiles
    if _nfiles >= 0:
        return _nfiles
    _tb = chess.syzygy.Tablebase()
    if not _DIR.is_dir():
        _nfiles = 0
        return 0
    try:
        _nfiles = _tb.add_directory(str(_DIR), load_wdl=True, load_dtz=True)
    except OSError:
        _nfiles = 0
    return _nfiles


def root_uci(board: chess.Board, legal: list[chess.Move]) -> str | None:
    """Best UCI among legal, or None if this position is not a 3-piece probe."""
    if not legal or board.castling_rights:
        return None
    if chess.popcount(board.occupied) > MAX_PIECES:
        return None
    if load() <= 0 or _tb is None:
        return None
    if _tb.get_wdl(board) is None:
        return None
    best: tuple[int, int] | None = None
    chosen: str | None = None
    for move in legal:
        board.push(move)
        try:
            if board.is_checkmate():
                key = (2, 10_000)
            else:
                wdl = _tb.get_wdl(board)
                if wdl is None:
                    continue
                dtz = _tb.get_dtz(board)
                key = (-wdl, 0 if dtz is None else dtz)
            if best is None or key > best:
                best = key
                chosen = move.uci()
        finally:
            board.pop()
    return chosen
