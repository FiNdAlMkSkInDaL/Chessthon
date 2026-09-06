"""Brick C gates: ply-adjusted TT mates, qsearch-in-check, SEE."""

from __future__ import annotations

from board_nb import from_fen, move_uci
from eval_nb import evaluate
from movegen_nb import generate_legal
from search_nb import MATE, qsearch_score, see
from tt_nb import EXACT, tt


def test_ply_adjusted_mates() -> None:
    tt.clear()
    for ply in range(1, 16):
        key = 0xC0FFEE00 + ply
        score = MATE - ply
        tt.store(key, 7, 8, EXACT, score, ply)
        hit = tt.probe(key)
        if hit is None:
            raise SystemExit(f"tt miss ply {ply}")
        got = tt.score_at(hit[3], ply + 2)
        want = score - 2
        if got != want:
            raise SystemExit(f"mate ply-adjust ply={ply}: got {got} want {want}")
        got_same = tt.score_at(hit[3], ply)
        if got_same != score:
            raise SystemExit(f"mate ply-adjust identity ply={ply}: got {got_same} want {score}")
        neg = -MATE + ply
        tt.store(key + 1000, 7, 8, EXACT, neg, ply)
        hitn = tt.probe(key + 1000)
        if hitn is None:
            raise SystemExit(f"tt miss neg ply {ply}")
        gotn = tt.score_at(hitn[3], ply + 2)
        if gotn != neg + 2:
            raise SystemExit(f"neg mate ply-adjust ply={ply}: got {gotn} want {neg + 2}")


def test_qsearch_in_check_no_standpat() -> None:
    # Black is checkmated. Stand-pat would return a quiet PeSTO; qsearch must be a mate score.
    fen = "5R1k/8/6K1/8/8/8/8/8 b - - 0 1"
    pos = from_fen(fen)
    stand = evaluate(pos)
    qs = qsearch_score(pos)
    if qs > -MATE + 64:
        raise SystemExit(f"qsearch in mate should be mate, got {qs} standpat={stand}")
    if qs == stand:
        raise SystemExit("qsearch stood pat in check")


def test_see_hanging_and_protected() -> None:
    pos = from_fen("4k3/8/8/8/8/8/7q/4K2R w K - 0 1")
    hanging = None
    for m in generate_legal(pos):
        if move_uci(m) == "h1h2":
            hanging = m
            break
    if hanging is None or see(pos, hanging) <= 0:
        raise SystemExit(f"Rxq hanging SEE should be > 0, got {hanging and see(pos, hanging)}")

    pos = from_fen("4k3/4p3/8/4Q3/8/8/8/4K3 w - - 0 1")
    qxpep = None
    for m in generate_legal(pos):
        if move_uci(m) == "e5e7":
            qxpep = m
            break
    if qxpep is None:
        raise SystemExit("missing Qxe7")
    if see(pos, qxpep) >= 0:
        raise SystemExit(f"Qxe7 protected by king SEE should be < 0, got {see(pos, qxpep)}")


def test_tt_persists() -> None:
    tt.clear()
    tt.store(12345, 99, 4, EXACT, 50, 0)
    tt.new_search()
    hit = tt.probe(12345)
    if hit is None or hit[0] != 99 or hit[3] != 50:
        raise SystemExit(f"tt should persist across new_search, got {hit}")


def test_bishop_pair_bonus() -> None:
    # White has both bishops; black has one. White to move.
    fen = "4k3/8/8/8/8/5b2/8/B2B2K1 w - - 0 1"
    pos = from_fen(fen)
    with_bp = evaluate(pos)
    fen_one = "4k3/8/8/8/8/5b2/8/3B2K1 w - - 0 1"
    without_bp = evaluate(from_fen(fen_one))
    if with_bp <= without_bp:
        raise SystemExit(
            f"bishop pair should raise eval: with={with_bp} without={without_bp}"
        )


def test_bishop_pair_numba_parity() -> None:
    """Python pesto vs pesto_nb on Linux signer only (laptop JIT is a liar)."""
    import sys

    if sys.platform.startswith("win"):
        return
    from eval_nb import pesto

    import core_nb

    fen = "4k3/8/8/8/8/5b2/8/B2B2K1 w - - 0 1"
    pos = from_fen(fen)
    py = pesto(pos, tempo=True)
    bb, mb, st = core_nb.pack_pos(pos)
    nb = int(core_nb.pesto_nb(bb, st, True))
    if py != nb:
        raise SystemExit(f"bishop-pair FEN pesto mismatch python={py} numba={nb}")
    fen_one = "4k3/8/8/8/8/5b2/8/3B2K1 w - - 0 1"
    pos1 = from_fen(fen_one)
    py1 = pesto(pos1, tempo=True)
    bb1, mb1, st1 = core_nb.pack_pos(pos1)
    nb1 = int(core_nb.pesto_nb(bb1, st1, True))
    if py1 != nb1:
        raise SystemExit(f"single-bishop FEN pesto mismatch python={py1} numba={nb1}")
    if py <= py1:
        raise SystemExit(f"pair should beat single: pair={py} single={py1}")


def main() -> None:
    test_ply_adjusted_mates()
    test_qsearch_in_check_no_standpat()
    test_see_hanging_and_protected()
    test_tt_persists()
    test_bishop_pair_bonus()
    test_bishop_pair_numba_parity()
    print("BRICK C OK")


if __name__ == "__main__":
    main()
