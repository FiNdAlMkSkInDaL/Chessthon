"""Pure-Python clock regression tests for the current 600-ply referee."""

from __future__ import annotations

import unittest

from odin.storm_clock import PLY_CAP, SearchClock, allocation, moves_to_go


class OdinClockTests(unittest.TestCase):
    def test_horizon_tracks_600_ply_cap_without_old_300_ply_collapse(self) -> None:
        self.assertEqual(PLY_CAP, 600)
        for ply in range(PLY_CAP + 1):
            horizon = moves_to_go(ply, phase=0)
            self.assertGreaterEqual(horizon, 1.0)
            self.assertLessEqual(horizon, max(1.0, (PLY_CAP - ply + 1) // 2))

        # Storm's 300-ply controller spent almost the entire remaining bank
        # here.  Odin must still forecast several decisions under the 600-ply
        # contract rather than manufacture a terminal situation.
        mode, soft_ms, hard_ms = allocation(20_000, 299, phase=0, root_moves=24)
        self.assertEqual(mode, "search")
        self.assertLess(soft_ms, 5_000.0)
        self.assertGreaterEqual(hard_ms, soft_ms)

    def test_root_effort_and_retry_evidence_affect_only_completed_depths(self) -> None:
        clock = SearchClock(1_000.0, 3_000.0, root_moves=24)
        clock.complete(1, 11, 20, 10.0, 100, root_effort=0.15)
        clock.complete(2, 11, 19, 30.0, 300, aspiration_failed=True, root_effort=0.25)
        self.assertGreater(clock.factor, 1.0)
        self.assertGreater(clock.target_ms, 1_000.0)
        self.assertTrue(clock.should_start(100.0))
        self.assertFalse(clock.should_start(3_001.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
