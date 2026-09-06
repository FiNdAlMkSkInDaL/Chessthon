"""Odin protocol/state regression tests against the pinned live referee.

Run with the repository Python 3.12:
``python -m unittest lab.odin.test_odin_state -v``.  This file deliberately
adds no submission data and imports Odin only through its isolated directory.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

import chess
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
ODIN = ROOT / "odin"
PINNED_STARTER = ROOT / "lab" / "odin" / "official-harness-91f70e54"

sys.path.insert(0, str(ODIN))
import history  # noqa: E402
from board_nb import from_fen  # noqa: E402


class FirstLegalAgent:
    def start(self, _budget: float) -> None:
        return None

    def stop(self) -> None:
        return None

    def move(self, fen: str, _clock: int) -> str:
        return next(iter(chess.Board(fen).legal_moves)).uci()


class MateOnCapAgent(FirstLegalAgent):
    def move(self, _fen: str, _clock: int) -> str:
        return "c2a2"


def pinned_referee():
    """Import the independent current starter, never the historical harness."""
    for name in tuple(sys.modules):
        if name == "harness" or name.startswith("harness."):
            del sys.modules[name]
    sys.path.insert(0, str(PINNED_STARTER))
    try:
        referee = importlib.import_module("harness.referee")
        rules = importlib.import_module("harness.rules")
    finally:
        sys.path.pop(0)
    if PINNED_STARTER not in Path(referee.__file__).resolve().parents:
        raise AssertionError(f"wrong referee import: {referee.__file__}")
    return referee, rules


class RefereeStateTests(unittest.TestCase):
    def tearDown(self) -> None:
        history.reset()

    def test_absolute_ply_comes_from_fen_not_request_count(self) -> None:
        cases = (
            ("7k/7p/8/8/8/8/P7/K7 w - - 0 300", 598),
            ("7k/7p/8/8/8/8/P7/K7 b - - 0 300", 599),
            ("7k/7p/8/8/8/8/P7/K7 w - - 0 301", 600),
        )
        for fen, expected in cases:
            history.observe_served(chess.Board(fen))
            self.assertEqual(history.absolute_ply(), expected)
            self.assertFalse(history.use_adjudication_eval())

    def test_ep_keys_match_python_chess_canonical_identity(self) -> None:
        # Impossible EP, pinned EP, then a genuine legal EP capture.
        cases = (
            (
                "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
                "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                True,
            ),
            (
                "4r1k1/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
                "4r1k1/8/8/3pP3/8/8/8/4K3 w - - 0 1",
                True,
            ),
            (
                "4r1k1/8/8/3pP3/8/8/8/2K5 w - d6 0 1",
                "4r1k1/8/8/3pP3/8/8/8/2K5 w - - 0 1",
                False,
            ),
        )
        for ep_fen, no_ep_fen, equal in cases:
            self.assertEqual(
                from_fen(ep_fen).key == from_fen(no_ep_fen).key,
                equal,
            )
            self.assertEqual(
                chess.Board(ep_fen)._transposition_key()
                == chess.Board(no_ep_fen)._transposition_key(),
                equal,
            )

    def test_current_referee_cap_and_mate_precedence(self) -> None:
        referee, rules = pinned_referee()
        self.assertEqual(rules.PLY_CAP, 600)
        cap_start = "7k/7p/8/8/8/8/P7/K7 b - - 0 300"
        capped = referee.play_match(
            FirstLegalAgent(), FirstLegalAgent(), 10_000, 0, start_fen=cap_start
        )
        self.assertEqual((capped.result, capped.termination), ("draw", "ply_cap"))

        mate_start = "7k/8/8/8/8/k7/2q5/K7 b - - 0 300"
        mated = referee.play_match(
            FirstLegalAgent(), MateOnCapAgent(), 10_000, 0, start_fen=mate_start
        )
        self.assertEqual((mated.result, mated.termination), ("black", "checkmate"))


class NativeStateTests(unittest.TestCase):
    def test_native_see_and_long_history_do_not_overrun(self) -> None:
        import core_nb
        from movegen_nb import generate_legal, move_uci

        fixtures = (
            ("5k2/6p1/8/8/8/8/1B6/4K1R1 w - - 0 1", "g1g7"),
            ("4k3/4b3/3p4/2B5/8/8/8/4R1K1 w - - 0 1", "c5d6"),
        )
        for fen, uci in fixtures:
            pos = from_fen(fen)
            move = next(m for m in generate_legal(pos) if move_uci(m) == uci)
            self.assertEqual(core_nb.see_nb(*core_nb.pack_pos(pos), move), 100)

        pos = from_fen("7k/7p/8/8/8/8/P7/K7 w - - 0 210")
        root = generate_legal(pos)
        real_history = list(range(1, 620)) + [pos.key]
        chosen = core_nb.search_root(pos, root, 120.0, 0.0, real_history, 418)
        self.assertIn(chosen, root)
        self.assertEqual(core_nb.last_info()["absolute_ply"], 418)
        trace = core_nb.last_info()["trace"]
        self.assertTrue(trace)
        self.assertTrue(all(
            entry["root_effort"] is None or 0.0 <= entry["root_effort"] <= 1.0
            for entry in trace
        ))

        first_history = np.uint64(core_nb.history_append(core_nb.HIST_SEED, 101))
        second_history = np.uint64(core_nb.history_append(core_nb.HIST_SEED, 202))
        self.assertNotEqual(
            core_nb.score_tt_key(pos.key, 0, 182, first_history),
            core_nb.score_tt_key(pos.key, 0, 182, second_history),
        )
        self.assertNotEqual(
            core_nb.score_tt_key(pos.key, 0, 182, first_history),
            core_nb.score_tt_key(pos.key, 98, 182, first_history),
        )
        self.assertNotEqual(
            core_nb.score_tt_key(pos.key, 0, 182, first_history),
            core_nb.score_tt_key(pos.key, 0, 1, first_history),
        )

        # NMP remains available in rich positions but never treats a sparse
        # queenless rook/minor ending as if a passing move were harmless.
        rook_end = core_nb.pack_pos(
            from_fen("7k/7p/8/8/8/8/P7/KR6 w - - 0 1")
        )[0]
        queen_position = core_nb.pack_pos(
            from_fen("6k1/7p/8/8/8/8/P5Q1/6K1 w - - 0 1")
        )[0]
        self.assertFalse(core_nb.nmp_safe_nb(rook_end))
        self.assertTrue(core_nb.nmp_safe_nb(queen_position))

        bb, mb, st = core_nb.pack_pos(from_fen("7k/7p/8/8/8/8/P7/K7 w - - 98 210"))
        before = st.copy()
        undo = np.zeros(7, dtype=np.uint64)
        core_nb.make_null(bb, mb, st, undo)
        self.assertEqual(st[core_nb.FIFTY], before[core_nb.FIFTY])
        core_nb.unmake_null(st, undo)
        self.assertTrue(np.array_equal(st, before))

    def test_native_cap_scores_draw_but_keeps_mate_precedence(self) -> None:
        import core_nb
        from movegen_nb import generate_legal, move_uci

        quiet = from_fen("7k/7p/8/8/8/8/P7/K7 b - - 0 300")
        quiet_root = generate_legal(quiet)
        core_nb.search_root(quiet, quiet_root, 120.0, 0.0, [quiet.key], 599)
        self.assertEqual(core_nb.last_info()["score"], 0)

        mate_fen = "8/8/8/8/8/k7/2q5/K7 b - - 0 300"
        self.assertTrue(chess.Board(mate_fen).is_valid())
        mate = from_fen(mate_fen)
        mate_root = generate_legal(mate)
        chosen = core_nb.search_root(mate, mate_root, 120.0, 0.0, [mate.key], 599)
        self.assertIn(chosen, mate_root)
        self.assertGreaterEqual(core_nb.last_info()["score"], 31_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
