"""Offline-fit invariants. The feature block is not release-enabled yet."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import chess

from lab.odin.training.features_ref import FEATURE_NAMES, extract


ROOT = Path(__file__).resolve().parents[2]


class OdinEvaluationExperimentTests(unittest.TestCase):
    def test_feature_geometry_is_colour_and_file_symmetric(self) -> None:
        boards = (
            chess.Board(),
            chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1"),
            chess.Board("4k3/P7/8/8/8/8/7p/4K3 w - - 0 1"),
            chess.Board("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"),
        )
        for board in boards:
            values = extract(board)
            self.assertEqual(extract(board.mirror()), tuple(-value for value in values))
            self.assertEqual(extract(board.transform(chess.flip_horizontal)), values)

    def test_frozen_opening_family_validation_improves_before_runtime_merge(self) -> None:
        report = json.loads((ROOT / "lab" / "odin" / "training" / "ridge-fit-sf19-n2000.json").read_text())
        self.assertEqual(report["feature_names"], list(FEATURE_NAMES))
        baseline = report["baseline"]["validation"]
        corrected = report["corrected"]["validation"]
        self.assertLess(corrected["mae_cp"], baseline["mae_cp"])
        self.assertLess(corrected["rmse_cp"], baseline["rmse_cp"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
