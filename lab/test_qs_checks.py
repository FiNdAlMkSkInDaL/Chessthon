"""Quiet-check qsearch: Rh1# must beat stand-pat. Does not use bishop-pair tests."""

from __future__ import annotations

from board_nb import from_fen, move_uci
from eval_nb import evaluate
from search_nb import MATE, qsearch_score


def test_quiet_rook_mate() -> None:
    # Back-rank: Re1# is a quiet check. Captures-only qsearch stands pat.
    fen = "6k1/5ppp/8/8/4r3/8/5PPP/6K1 b - - 0 1"
    pos = from_fen(fen)
    stand = evaluate(pos)
    qs = qsearch_score(pos)
    if qs <= stand:
        raise SystemExit(f"qsearch must beat stand-pat with Re1#: qs={qs} stand={stand}")
    if qs < MATE - 64:
        raise SystemExit(f"qsearch should be a mate score, got {qs} stand={stand}")


def test_backrank_check_listed() -> None:
    from movegen_nb import generate_quiet_checks

    fen = "6k1/5ppp/8/8/4r3/8/5PPP/6K1 b - - 0 1"
    pos = from_fen(fen)
    uci = {move_uci(m) for m in generate_quiet_checks(pos)}
    if "e4e1" not in uci:
        raise SystemExit(f"expected Re1# in quiet checks, got {sorted(uci)}")


def main() -> None:
    test_quiet_rook_mate()
    test_backrank_check_listed()
    print("QS CHECKS OK")


if __name__ == "__main__":
    main()
