"""Regression gate for the no-depth-one-under-200ms clock rule."""

from __future__ import annotations

import sys
import types

from board_nb import START_FEN, from_fen
from movegen_nb import generate_legal
from time_nb import MIN_ITER_MS


def test_python_fallback_keeps_the_seeded_legal_move() -> None:
    """Force the fallback path; it must not start its unabortable depth one."""
    import search_nb

    pos = from_fen(START_FEN)
    root = generate_legal(pos)
    previous = sys.modules.get("core_nb")
    sys.modules["core_nb"] = types.SimpleNamespace(HAS_NUMBA=False, NUMBA_READY=False)
    try:
        best = search_nb.iterative_deepening(
            pos,
            root,
            hard_ms=float(MIN_ITER_MS - 1),
            soft_ms=0.0,
            adjudicate=False,
            game_zkeys=[],
        )
    finally:
        if previous is None:
            del sys.modules["core_nb"]
        else:
            sys.modules["core_nb"] = previous
    if best not in root:
        raise SystemExit("fallback did not retain a legal root move")
    if search_nb._nodes != 0:
        raise SystemExit("fallback started a depth-one search below MIN_ITER_MS")


def main() -> None:
    test_python_fallback_keeps_the_seeded_legal_move()
    print("ITERATION START OK")


if __name__ == "__main__":
    main()
