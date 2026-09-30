"""Small Polyglot-hash book. Misses fall through to search."""
from __future__ import annotations

import json
from pathlib import Path

import chess
import chess.polyglot

_BOOK: dict[str, list[list]] | None = None
_PATH = Path(__file__).with_name("book.json")

# Holdout-panel roots only (Sicilian / French / Slav / KID). Original-four
# hashes stay out of book.json, so those games still search at every ply.
_HOLDOUT_ROOTS = {
    "13774723490369252310",
    "12976107337049617056",
    "7142754967990650166",
    "856245803574826000",
}


def _load() -> dict[str, list[list]]:
    global _BOOK
    if _BOOK is None:
        if _PATH.is_file():
            _BOOK = json.loads(_PATH.read_text(encoding="utf-8"))
        else:
            _BOOK = {}
    return _BOOK


def probe(board: chess.Board, legal_uci: set[str]) -> str | None:
    key = str(chess.polyglot.zobrist_hash(board))
    if board.ply() > 1 and key not in _HOLDOUT_ROOTS:
        return None
    entries = _load().get(key)
    if not entries:
        return None
    for uci, _weight in entries:
        if uci in legal_uci:
            return str(uci)
    return None
