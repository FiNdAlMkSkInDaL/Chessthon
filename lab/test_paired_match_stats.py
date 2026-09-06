"""Synthetic, Docker-free tests for the paired release statistics gate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lab.paired_match_stats import analyze_rows, read_jsonl


def container_game(
    pair: int,
    game: int,
    colour: str,
    result: str,
    *,
    fen: str | None = None,
    termination: str = "checkmate",
    candidate_failure: bool = False,
    candidate_sha: str = "candidate-sha",
    baseline_sha: str = "baseline-sha",
) -> dict:
    candidate_white = colour == "white"
    return {
        "type": "game",
        "run_id": "synthetic-run",
        "pair": pair,
        "game": game,
        "opening_index": pair + 100,
        "fen": fen or f"synthetic-fen-{pair}",
        "white_role": "candidate" if candidate_white else "baseline",
        "black_role": "baseline" if candidate_white else "candidate",
        "white_sha256": candidate_sha if candidate_white else baseline_sha,
        "black_sha256": baseline_sha if candidate_white else candidate_sha,
        "result": result,
        "termination": termination,
        "candidate_points": (
            0.5 if result == "draw" else float(result == colour) if result != "void" else None
        ),
        "candidate_failure": candidate_failure,
    }


def pair_rows(pair: int, first: str, second: str) -> list[dict]:
    return [
        container_game(pair, pair * 2 - 1, "white", first),
        container_game(pair, pair * 2, "black", second),
    ]


class PairedMatchStatsTests(unittest.TestCase):
    def analyze(self, rows: list[dict], **kwargs) -> dict:
        return analyze_rows(
            rows,
            bootstrap_samples=1_000,
            seed=12345,
            min_pairs=kwargs.pop("min_pairs", 1),
            **kwargs,
        )

    def test_wdl_and_pentanomial_use_complete_pairs(self) -> None:
        rows = []
        rows += pair_rows(1, "white", "black")  # WW
        rows += pair_rows(2, "white", "draw")   # WD
        rows += pair_rows(3, "white", "white")  # WL => DD score bucket
        stats = self.analyze(rows)
        self.assertEqual((stats["wins"], stats["draws"], stats["losses"]), (4, 1, 1))
        self.assertAlmostEqual(stats["score"], 0.75)
        self.assertEqual(
            stats["pentanomial"], {"LL": 0, "LD": 0, "DD": 1, "WD": 1, "WW": 1}
        )
        self.assertEqual(stats["validation_errors"], [])

    def test_strong_result_passes_only_after_minimum_pairs(self) -> None:
        rows = []
        for pair in range(1, 31):
            rows += pair_rows(pair, "white", "black")
        passed = self.analyze(rows, min_pairs=20)
        self.assertEqual(passed["verdict"], "PASS")
        self.assertEqual(passed["bootstrap"]["score_ci"], [1.0, 1.0])
        self.assertEqual(passed["elo"]["estimate"], "+inf")

        held = self.analyze(rows[:20], min_pairs=20)
        self.assertEqual(held["verdict"], "FAIL")
        self.assertTrue(any("need 20 valid pairs" in reason for reason in held["reasons"]))

    def test_candidate_failure_excludes_pair_and_forces_fail(self) -> None:
        rows = []
        rows += pair_rows(1, "white", "black")
        rows += [
            container_game(
                2,
                3,
                "white",
                "black",
                termination="illegal",
                candidate_failure=True,
            ),
            container_game(2, 4, "black", "black"),
        ]
        stats = self.analyze(rows)
        self.assertEqual(stats["included_pairs"], 1)
        self.assertEqual(stats["excluded_failure_pairs"], 1)
        self.assertEqual(stats["candidate_failures"], {"illegal": 1})
        self.assertEqual(stats["verdict"], "FAIL")

    def test_opponent_failure_is_inferred_and_excluded(self) -> None:
        rows = []
        rows += pair_rows(1, "white", "black")
        rows += [
            container_game(2, 3, "white", "white", termination="flag"),
            container_game(2, 4, "black", "black"),
        ]
        stats = self.analyze(rows)
        self.assertEqual(stats["opponent_failures"], {"flag": 1})
        self.assertEqual(stats["excluded_failure_pairs"], 1)
        self.assertEqual(stats["candidate_failures"], {})

    def test_colour_or_fen_mismatch_is_validation_failure(self) -> None:
        rows = [
            container_game(1, 1, "white", "white", fen="fen-a"),
            container_game(1, 2, "white", "white", fen="fen-b"),
        ]
        stats = self.analyze(rows)
        self.assertEqual(stats["verdict"], "FAIL")
        self.assertEqual(stats["included_pairs"], 0)
        joined = "\n".join(stats["validation_errors"])
        self.assertIn("different FENs", joined)
        self.assertIn("colours were not swapped", joined)

    def test_incomplete_pair_flags_failure_and_validation(self) -> None:
        rows = [
            container_game(
                1,
                1,
                "white",
                "black",
                termination="crash",
                candidate_failure=True,
            )
        ]
        stats = self.analyze(rows)
        self.assertEqual(stats["candidate_failures"], {"crash": 1})
        self.assertTrue(stats["validation_errors"])
        self.assertEqual(stats["verdict"], "FAIL")

    def test_bootstrap_is_deterministic_and_threshold_is_configurable(self) -> None:
        rows = []
        for pair in range(1, 21):
            if pair % 4 == 0:
                rows += pair_rows(pair, "black", "white")  # LL
            else:
                rows += pair_rows(pair, "white", "black")  # WW
        first = self.analyze(rows, threshold=0.49)
        second = self.analyze(rows, threshold=0.49)
        self.assertEqual(first["bootstrap"], second["bootstrap"])
        self.assertGreater(first["bootstrap"]["score_ci"][0], 0.49)
        self.assertEqual(first["verdict"], "PASS")

    def test_mixed_archive_identities_cannot_pass_as_one_candidate(self) -> None:
        rows = []
        rows += pair_rows(1, "white", "black")
        rows += [
            container_game(2, 3, "white", "white", candidate_sha="other-candidate"),
            container_game(2, 4, "black", "black", candidate_sha="other-candidate"),
        ]
        stats = self.analyze(rows)
        self.assertEqual(stats["verdict"], "FAIL")
        self.assertEqual(
            stats["identities"]["candidate"],
            ["candidate-sha", "other-candidate"],
        )
        self.assertTrue(
            any("mix candidate identities" in error for error in stats["validation_errors"])
        )

    def test_legacy_gauntlet_and_metadata_rows(self) -> None:
        fen = "legacy-fen"
        rows = [
            {"type": "run_start", "run_id": "ignored"},
            {
                "game": 1,
                "we": "white",
                "fen": fen,
                "result": "draw",
                "termination": "stalemate",
                "our_fail": False,
                "their_fail": False,
                "white": "/candidate",
                "black": "/baseline",
            },
            {
                "game": 2,
                "we": "black",
                "fen": fen,
                "result": "black",
                "termination": "checkmate",
                "our_fail": False,
                "their_fail": False,
                "white": "/baseline",
                "black": "/candidate",
            },
            {"type": "run_summary", "games_completed": 2},
        ]
        stats = self.analyze(rows)
        self.assertEqual((stats["wins"], stats["draws"], stats["losses"]), (1, 1, 0))
        self.assertEqual(stats["pentanomial"]["WD"], 1)

    def test_jsonl_reader_reports_bad_lines_and_keeps_games(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "match.jsonl"
            game = container_game(1, 1, "white", "white")
            path.write_text(
                json.dumps({"type": "run_start"})
                + "\n{broken\n"
                + json.dumps(game)
                + "\n",
                encoding="utf-8",
            )
            rows, errors = read_jsonl([path])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid JSON", errors[0])


if __name__ == "__main__":
    unittest.main()
