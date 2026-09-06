"""Clock policy invariants and synthetic search traces; no engine JIT needed."""

import random
import unittest

from storm.storm_clock import (
    HARD_MARGIN_MS,
    SearchClock,
    allocation,
    moves_to_go,
    phase_units,
)


def feed(clock, moves, scores, times=None, failures=None):
    times = times or [3.0 * 2 ** i for i in range(len(moves))]
    failures = failures or [False] * len(moves)
    for depth, (move, score, elapsed, failed) in enumerate(
        zip(moves, scores, times, failures), 1
    ):
        clock.complete(depth, move, score, elapsed, int(elapsed * 300), failed)
    return clock


class AllocationTests(unittest.TestCase):
    def test_hard_cap_never_borrows_pending_increment(self):
        rng = random.Random(8147)
        for _ in range(4000):
            left = rng.randrange(-100, 300_000)
            mode, soft, hard = allocation(
                left, rng.randrange(301), rng.randrange(30), rng.randrange(1, 60),
                bool(rng.randrange(2)),
            )
            self.assertLessEqual(hard, max(0, left - HARD_MARGIN_MS))
            self.assertGreaterEqual(soft, 0)
            self.assertLessEqual(soft, hard)
            self.assertEqual(mode == "panic", hard == 0)
        for left in (0, 200, 400, 449):
            self.assertEqual(allocation(left, 0), ("panic", 0.0, 0.0))

    def test_small_real_allowance_can_search(self):
        mode, soft, hard = allocation(500, 0)
        self.assertEqual(mode, "search")
        self.assertTrue(SearchClock(soft, hard).should_start(0))
        self.assertFalse(SearchClock(soft, hard).should_start(hard))

    def test_horizon_uses_material_and_game_age(self):
        self.assertGreater(moves_to_go(0, 24), moves_to_go(0, 8))
        self.assertGreater(moves_to_go(0, 24), moves_to_go(60, 24))
        self.assertEqual(moves_to_go(0, 0), 18)
        self.assertEqual(moves_to_go(60, 0), 8)
        self.assertEqual(moves_to_go(296, 24), 2)
        self.assertEqual(moves_to_go(298, 24), 1)
        self.assertEqual(moves_to_go(299, 24), 1)

    def test_phase_is_capped_and_does_not_count_pawns_or_kings(self):
        self.assertEqual(phase_units([255, 3, 3, 3, 1, 1] * 2), 24)
        self.assertEqual(phase_units([255, 0, 0, 0, 0, 1] * 2), 0)
        self.assertEqual(phase_units([255, 0, 0, 0, 255, 1] * 2), 24)

    def test_single_move_is_cheap_but_two_moves_are_not_assumed_easy(self):
        _, single, _ = allocation(120_000, 0, root_moves=1)
        _, pair, _ = allocation(120_000, 0, root_moves=2)
        _, many, _ = allocation(120_000, 0, root_moves=40)
        self.assertLess(single, pair / 20)
        self.assertEqual(pair, many)

    def test_synthetic_long_game_spends_bank_and_retains_floor(self):
        # Allocation-only simulation is a policy sanity check, not an Elo test.
        # A normal game sheds material and gradually converts the bank to depth.
        left = 120_000.0
        for turn in range(65):
            phase = max(0, 24 - turn * 0.6)
            mode, soft, hard = allocation(int(left), 2 * turn, phase)
            self.assertEqual(mode, "search")
            left -= soft
            self.assertGreaterEqual(left, HARD_MARGIN_MS)
            left += 500  # Only after this move has returned.
        self.assertLess(left, 5_000)


class SearchClockTests(unittest.TestCase):
    def test_volatile_middlegame_earns_more_than_stable_move(self):
        stable = feed(SearchClock(4000, 13_000), [1] * 5, [30, 35, 32, 34, 33])
        uncertain = feed(SearchClock(4000, 13_000),
                         [1, 2, 1, 3, 4], [30, 10, 45, 20, -100],
                         failures=[False, True, True, False, True])
        self.assertLess(stable.target_ms, 3000)
        self.assertGreater(uncertain.target_ms, 8000)
        self.assertLessEqual(uncertain.target_ms, uncertain.hard_ms)

    def test_large_static_advantage_does_not_imply_easy_conversion(self):
        even = feed(SearchClock(4000, 13_000), [1, 2, 3], [20, 25, 15])
        winning = feed(SearchClock(4000, 13_000), [1, 2, 3], [1020, 1025, 1015])
        self.assertEqual(even.target_ms, winning.target_ms)

    def test_same_pv_score_collapse_and_failures_extend_time(self):
        stable = feed(SearchClock(4000, 13_000), [1] * 3, [100, 100, 100])
        collapse = feed(SearchClock(4000, 13_000), [1] * 3, [100, 100, -100])
        failed = feed(SearchClock(4000, 13_000), [1] * 3, [100, 100, 100],
                      failures=[False, False, True])
        self.assertGreater(collapse.target_ms, stable.target_ms)
        self.assertGreater(failed.target_ms, stable.target_ms)

    def test_mate_and_forced_move_stop_after_completed_result(self):
        mate = feed(SearchClock(4000, 13_000), [1], [31_999])
        forced = feed(SearchClock(30, 100, root_moves=1), [1], [0])
        self.assertFalse(mate.should_start(5))
        self.assertFalse(forced.should_start(5))

    def test_no_machine_nps_guess_can_stop_initial_iterations(self):
        clock = SearchClock(5, 100)
        self.assertTrue(clock.should_start(0))
        clock.complete(1, 1, 20, 10, 1_000_000)
        self.assertTrue(clock.should_start(10))
        clock.complete(2, 1, 20, 10, 1_000_000)
        self.assertTrue(clock.should_start(20))
        self.assertFalse(clock.should_start(100))

    def test_observed_iteration_growth_avoids_unfinishable_pass(self):
        clock = feed(SearchClock(4000, 5000), [1] * 3, [0] * 3,
                     times=[100, 500, 2500])
        self.assertAlmostEqual(clock.predicted_next_ms, 12_500)
        self.assertFalse(clock.should_start(3100))

    def test_odd_even_growth_is_tempered(self):
        clock = feed(SearchClock(4000, 13_000), [1] * 5, [0] * 5,
                     times=[10, 100, 50, 500, 250])
        self.assertAlmostEqual(clock.predicted_next_ms, 250 * 5 ** 0.5)

    def test_recent_changing_moves_remain_uncertain_after_one_stable_depth(self):
        clock = feed(SearchClock(4000, 13_000), [1, 2, 3, 4, 4], [0] * 5)
        self.assertGreater(clock.factor, 1.0)

    def test_root_effort_only_supports_established_stability(self):
        clock = feed(SearchClock(4000, 13_000), [1, 1], [0, 0])
        clock.complete(3, 1, 0, 12, 3600, root_effort=0.95)
        plain = feed(SearchClock(4000, 13_000), [1] * 3, [0] * 3)
        self.assertLess(clock.target_ms, plain.target_ms)

    def test_duplicate_depth_is_not_extra_stability(self):
        clock = feed(SearchClock(4000, 13_000), [1], [0])
        with self.assertRaises(ValueError):
            clock.complete(1, 1, 0, 10, 100)


if __name__ == "__main__":
    unittest.main()
