"""Late-game clock floor. Does not import agent (laptop JIT)."""

from __future__ import annotations

from time_nb import allocation

try:
    from time_nb import early_stop_ok, soft_budget
except ImportError:
    early_stop_ok = None  # type: ignore[misc, assignment]
    soft_budget = None  # type: ignore[misc, assignment]


def test_panic() -> None:
    mode, soft, hard = allocation(200, 0)
    if mode != "panic" or soft or hard:
        raise SystemExit(f"panic want ('panic',0,0) got {(mode, soft, hard)}")


def test_start_hard_is_a_slice_of_the_clock() -> None:
    mode, _soft, hard = allocation(120_000, 0)
    if mode != "search":
        raise SystemExit(f"startpos allocation should search, got {mode}")
    if hard < 5_000 or hard > 8_000:
        raise SystemExit(f"start hard should be ~6.4s, got {hard}")


def test_late_game_unstarves() -> None:
    _, _, early = allocation(120_000, 0)
    _, _, late = allocation(120_000, 280)
    if late <= early:
        raise SystemExit(f"ply 280 hard {late} should exceed ply 0 hard {early}")
    if late < 20_000:
        raise SystemExit(
            f"ply 280 remaining_our should drop below the old floor of 20, hard={late}"
        )


def test_soft_budget_extends_after_aspiration_miss() -> None:
    if soft_budget is None:
        return
    soft = 1000.0
    if soft_budget(soft, asp_failed=False) != soft:
        raise SystemExit("base soft should be unchanged")
    if soft_budget(soft, asp_failed=True) != soft * 1.15:
        raise SystemExit("aspiration miss should extend soft by 15%")


def test_early_stop_requires_stable_pv() -> None:
    if early_stop_ok is None:
        return
    soft = 1000.0
    if early_stop_ok(879, soft, depth=4, pv_stable=True):
        raise SystemExit("early stop should need >= 88% of soft")
    if not early_stop_ok(880, soft, depth=4, pv_stable=True):
        raise SystemExit("stable PV at 88% soft should allow early stop")
    if early_stop_ok(900, soft, depth=4, pv_stable=False):
        raise SystemExit("unstable PV must not early-stop")
    if early_stop_ok(900, soft, depth=3, pv_stable=True):
        raise SystemExit("depth < 4 must not early-stop")


def main() -> None:
    test_panic()
    test_start_hard_is_a_slice_of_the_clock()
    test_late_game_unstarves()
    test_soft_budget_extends_after_aspiration_miss()
    test_early_stop_requires_stable_pv()
    print("TIME OK")


if __name__ == "__main__":
    main()
