"""Regression gate for the iterative-deepening node budget.

The Numba search keeps a cumulative node counter.  A time allowance for the
next depth must be converted to an absolute counter limit before it reaches
the jitted stop check.
"""

from __future__ import annotations

from core_nb import iteration_node_limit


def test_depth_one_is_unbounded() -> None:
    if iteration_node_limit(9_999_999, 1.0, 1.0, 1) != 10**15:
        raise SystemExit("depth-one search must not use a stale node estimate")


def test_later_depth_adds_the_cumulative_counter() -> None:
    nodes_before = 1_250_000
    remaining_ms = 3_200.0
    nps = 700_000.0
    allowance = int(max(8_000.0, (remaining_ms / 1000.0) * nps * 0.85))
    got = iteration_node_limit(nodes_before, remaining_ms, nps, 6)
    want = nodes_before + allowance
    if got != want:
        raise SystemExit(f"node limit={got}, want cumulative {want}")
    if got <= allowance:
        raise SystemExit("later depth reused an absolute, already-spent budget")


def test_minimum_allowance_still_advances() -> None:
    nodes_before = 99_001
    got = iteration_node_limit(nodes_before, 0.1, 10.0, 2)
    if got != nodes_before + 8_000:
        raise SystemExit(f"minimum node allowance lost cumulative offset: {got}")


def main() -> None:
    test_depth_one_is_unbounded()
    test_later_depth_adds_the_cumulative_counter()
    test_minimum_allowance_still_advances()
    print("NODE BUDGET OK")


if __name__ == "__main__":
    main()
