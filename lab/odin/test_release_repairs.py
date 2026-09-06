"""Lightweight release regressions; no Numba compilation or agent import.

The NMP tests execute the actual negamax function body through the real null
fail-high/verification branch, substituting deterministic child-search scores.
This checks bound direction independently of a position accidentally masking
the error. Native engine gates remain a separate required check.
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import patch

import chess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "odin"))


class SparseVerificationRegression(unittest.TestCase):
    def _exercise(self, beta: int) -> None:
        source = ast.parse((ROOT / "odin/core_nb.py").read_text(encoding="utf-8"))
        function = copy.deepcopy(next(n for n in source.body
                                     if isinstance(n, ast.FunctionDef) and n.name == "negamax_nb"))
        function.decorator_list = []
        names = [arg.arg for arg in function.args.args]
        env = dict(np=np, MAX_PLY=96, MATE=32000, MATE_WIN=31000,
                   DRAW=0, CHECK_EXT_PLY=48, RFP_MAX_D=6, RFP_MARGIN=80,
                   NMP_MIN_D=3, SIDE=3, KEY=8, FIFTY=6, U_CAP=0,
                   EXACT=0, LOWER=1, UPPER=2)
        env.update(check_clock=lambda *args: False,
                   in_check_nb=lambda *args: False,
                   count_key=lambda *args: 0,
                   insufficient_material_nb=lambda *args: False,
                   history_append=lambda sig, key: sig,
                   score_tt_key=lambda *args: np.uint64(1),
                   tt_probe=lambda *args: (False, 0, 0, 0, 0),
                   evaluate_nb=lambda *args: beta + 50,
                   has_nm_pieces=lambda *args: True,
                   nmp_safe_nb=lambda *args: False)
        values = {name: 0 for name in names}
        values.update(bb=np.zeros(12, np.uint64), mb=np.zeros(64, np.int8),
                      st=np.zeros(12, np.uint64), depth=7, alpha=beta - 1,
                      beta=beta, ply=0, hist=np.zeros(104, np.uint64), hlen=0,
                      adjudicate=False, cap_left=600, has_pair=False,
                      hist_sig=np.uint64(1), undos=np.zeros((4, 7), np.uint64),
                      stacks=np.zeros((4, 256), np.int32),
                      scratches=np.zeros((4, 256), np.int32),
                      nodes=np.zeros(2, np.int64), aborted=np.zeros(1, np.int32))
        values["st"][8] = 123
        before = values["st"].copy()
        calls = []

        def make_null(_bb, _mb, state, _undo):
            state[3] ^= np.uint64(1)

        def unmake_null(state, _undo):
            state[:] = before

        def child(*args):
            call = dict(zip(names, args))
            calls.append(call)
            if len(calls) == 1:
                self.assertEqual(int(call["st"][3]), 1)
                self.assertEqual((call["alpha"], call["beta"]), (-beta, -beta + 1))
                self.assertEqual(call["cap_left"], 600)
                return -beta  # manufacture the null fail-high being checked
            self.assertTrue(np.array_equal(call["st"], before))
            self.assertEqual(call["ply"], 0)
            self.assertTrue(call["adjudicate"])  # verification disables aggressive pruning
            self.assertEqual((call["alpha"], call["beta"]), (beta - 1, beta))
            self.assertEqual(call["cap_left"], 600)
            return beta

        env.update(make_null=make_null, unmake_null=unmake_null)
        exec(compile(ast.Module(body=[function], type_ignores=[]), "<actual-negamax-body>", "exec"), env)
        actual = env["negamax_nb"]
        env["negamax_nb"] = child
        result = actual(**values)
        self.assertEqual(result, beta)
        self.assertEqual(len(calls), 2)
        self.assertTrue(np.array_equal(values["st"], before))

    def test_positive_beta_real_side_verification(self):
        self._exercise(100)

    def test_negative_beta_real_side_verification(self):
        self._exercise(-100)

    def test_negative_beta_upper_bound_counterexample(self):
        # Real MAX position: one move, then opponent can choose scores50 or200.
        # Its true value is -200. A wrong [100,101] window searches the child
        # with [-101,-100], returns early at50, and produces upper-bound -50.
        def child_search(alpha, beta):
            best = -32001
            for value in (50, 200):
                best = max(best, value)
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return best

        threshold = -100
        wrong = -child_search(-101, -100)
        correct = -child_search(100, 101)
        self.assertEqual(wrong, -50)
        self.assertGreaterEqual(wrong, threshold)
        self.assertEqual(correct, -200)
        self.assertLess(correct, threshold)


class FallbackDeadlineRegression(unittest.TestCase):
    def test_numba_unready_tactical_fallback_restores_position_and_stops(self):
        import board_nb
        import movegen_nb
        import search_nb

        position = board_nb.from_fen(
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 10")
        legal = movegen_nb.generate_legal(position)
        before = {name: copy.deepcopy(getattr(position, name)) for name in position.__slots__}
        unavailable = types.SimpleNamespace(HAS_NUMBA=True, NUMBA_READY=False)
        started = time.perf_counter()
        with patch.dict(sys.modules, {"core_nb": unavailable}):
            choice = search_nb.iterative_deepening(
                position, legal, hard_ms=260.0, soft_ms=260.0,
                game_zkeys=[position.key], absolute_ply=18)
        elapsed = time.perf_counter() - started
        self.assertIn(choice, legal)
        self.assertGreater(search_nb._nodes, 0)
        self.assertTrue(search_nb._aborted)
        self.assertLess(elapsed, 0.60)
        for name, value in before.items():
            self.assertEqual(getattr(position, name), value, name)


class FiftyClaimRegression(unittest.TestCase):
    def test_native_function_body_matches_reference_at_rule50_boundaries(self):
        source = ast.parse((ROOT / "odin/core_nb.py").read_text(encoding="utf-8"))
        function = copy.deepcopy(next(n for n in source.body
                                     if isinstance(n, ast.FunctionDef) and n.name == "fifty_claim_nb"))
        function.decorator_list = []
        for halfmove in (0, 5, 98, 99, 100):
            with self.subTest(halfmove=halfmove):
                board = chess.Board(f"6n1/6kp/8/8/8/P7/8/KN5R w - - {halfmove} 6")
                initial = board.fen()
                legal = list(board.legal_moves)
                mailbox = np.full(64, -1, np.int8)
                for square, piece in board.piece_map().items():
                    mailbox[square] = (0 if piece.color else 6) + piece.piece_type - 1
                state = np.zeros(12, np.uint64)
                state[6] = halfmove
                pushes = []

                def make(_bb, _mb, _st, index, _undo):
                    pushes.append(index)
                    board.push(legal[index])

                def unmake(*_args):
                    board.pop()

                env = dict(np=np, FIFTY=6, m_from=lambda index: legal[index].from_square,
                           m_cap=lambda index: board.is_capture(legal[index]),
                           make_nb=make, unmake_nb=unmake,
                           has_legal_nb=lambda *_args: bool(list(board.legal_moves)))
                exec(compile(ast.Module(body=[function], type_ignores=[]), "<actual-fifty-body>", "exec"), env)
                observed = env["fifty_claim_nb"](
                    None, mailbox, state, list(range(len(legal))), len(legal), None, None)
                self.assertEqual(observed, board.can_claim_fifty_moves())
                self.assertEqual(board.fen(), initial)
                if halfmove < 99:
                    self.assertEqual(pushes, [])

    def test_fallback_rule50_boundaries_and_old_pair_after_zeroing(self):
        import board_nb
        import movegen_nb
        import search_nb

        board = chess.Board("6nk/7p/8/8/8/8/P7/KN5R w - - 0 1")
        history = [board_nb.from_fen(board.fen()).key]
        for uci in ("b1c3", "g8f6", "c3b1", "f6g8", "a2a3",
                    "g8f6", "b1c3", "f6g8", "c3b1", "h8g7"):
            board.push_uci(uci)
            history.append(board_nb.from_fen(board.fen()).key)
        self.assertFalse(board.can_claim_threefold_repetition())
        self.assertFalse(board.can_claim_fifty_moves())
        self.assertEqual(board.halfmove_clock, 5)
        position = board_nb.from_fen(board.fen())
        self.assertTrue(search_nb._has_repetition_pair(history[:-1], position.key))
        old_abort, old_mode = search_nb._allow_abort, search_nb._adjudicate
        try:
            search_nb._allow_abort = False
            search_nb._adjudicate = True
            score = search_nb._qsearch(position, -search_nb.INF, search_nb.INF,
                                      0, history[:-1], 600 - board.ply())
        finally:
            search_nb._allow_abort, search_nb._adjudicate = old_abort, old_mode
        self.assertGreater(score, 200, "old pair must not fabricate a fifty-move draw")
        for halfmove in (0, 5, 98, 99, 100):
            board.halfmove_clock = halfmove
            position = board_nb.from_fen(board.fen())
            observed = search_nb._fifty_claim_from_legal(position, movegen_nb.generate_legal(position))
            self.assertEqual(observed, board.can_claim_fifty_moves(), halfmove)


class CapDepthBoundaryRegression(unittest.TestCase):
    def test_cap_mate_precedence_at_maximum_ply_without_stack_overrun(self):
        tree = ast.parse((ROOT / "odin/core_nb.py").read_text(encoding="utf-8"))
        quiet = chess.Board("8/8/8/8/8/k7/2q5/K7 b - - 0 300")
        self.assertTrue(quiet.is_valid())
        mate = quiet.copy()
        mate.push_uci("c2a2")
        self.assertTrue(mate.is_checkmate())
        for name in ("qsearch_nb", "negamax_nb"):
            function = copy.deepcopy(next(n for n in tree.body
                                         if isinstance(n, ast.FunctionDef) and n.name == name))
            function.decorator_list = []
            for board, expected in ((quiet, 0), (mate, -32000 + 96)):
                with self.subTest(function=name, checkmate=board.is_checkmate()):
                    def legal(_bb, _mb, _st, moves, scratch):
                        self.assertEqual(moves.shape, (256,))
                        self.assertEqual(scratch.shape, (256,))
                        return len(list(board.legal_moves))

                    env = dict(np=np, MAX_PLY=96, MAX_MOVES=256, MATE=32000,
                               DRAW=0, SIDE=3, check_clock=lambda *_args: False,
                               in_check_nb=lambda *_args: board.is_check(), gen_legal=legal,
                               evaluate_nb=lambda *_args: 987)
                    exec(compile(ast.Module(body=[function], type_ignores=[]), "<actual-cap-boundary>", "exec"), env)
                    values = {arg.arg: 0 for arg in function.args.args}
                    values.update(ply=96, cap_left=0, st=np.zeros(12, np.uint64),
                                  stacks=np.zeros((96, 256), np.int32),
                                  scratches=np.zeros((96, 256), np.int32),
                                  nodes=np.zeros(2, np.int64))
                    before = values["st"].copy()
                    self.assertEqual(env[name](**values), expected)
                    self.assertTrue(np.array_equal(values["st"], before))

        import board_nb
        import search_nb
        old_abort = search_nb._allow_abort
        try:
            search_nb._allow_abort = False
            for board, expected in ((quiet, 0), (mate, -32000 + 96)):
                position = board_nb.from_fen(board.fen())
                self.assertEqual(search_nb._qsearch(position, -32001, 32001, 96, [], 0), expected)
                self.assertEqual(search_nb._negamax(position, 0, -32001, 32001, 96, [], 0), expected)
        finally:
            search_nb._allow_abort = old_abort


if __name__ == "__main__":
    unittest.main(verbosity=2)
