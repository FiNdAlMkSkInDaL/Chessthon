"""Lightweight source-body and real fallback gates; no native compilation.

The native integration/performance gate remains required on the Linux signer.
"""
from __future__ import annotations
import ast
from collections import Counter
import copy
import hashlib
import itertools
import inspect
import json
from pathlib import Path
import random
import sys
import types
import unittest

import chess
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "odin_compact_guard"
sys.path.insert(0, str(SOURCE))
import board_nb
import history
import movegen_nb
import search_nb


def source_functions(names, env=None):
    tree = ast.parse((SOURCE / "core_nb.py").read_text(encoding="utf-8"))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node = copy.deepcopy(node)
            node.decorator_list = []
            selected.append(node)
    assert {n.name for n in selected} == set(names)
    ns = dict(np=np, TT_SIZE=64, TT_MASK=63, MOVE_HINT_MASK=15,
              HIST_SEED=np.uint64(0xCBF29CE484222325), NULL_HIST_SEED=np.uint64(0x84222325CBF29CE4),
              CTX_FIFTY=np.uint64(0x9E3779B185EBCA87),
              CTX_CAP=np.uint64(0xC2B2AE3D27D4EB4F), MATE_WIN=31000)
    ns.update(env or {})
    exec(compile(ast.Module(body=selected, type_ignores=[]), "<actual-native-bodies>", "exec"), ns)
    return ns


HELPERS = ("history_append", "score_tt_key", "move_hint_probe", "move_hint_store",
           "tt_probe", "tt_store", "tt_to", "tt_from", "count_key", "history_has_pair")


class ContextIdentityTests(unittest.TestCase):
    def setUp(self):
        self.c = source_functions(HELPERS)
        self.warning_policy = np.errstate(over="ignore")
        self.warning_policy.__enter__()

    def tearDown(self):
        self.warning_policy.__exit__(None, None, None)

    def signature(self, keys):
        value = self.c["HIST_SEED"]
        for key in keys:
            value = self.c["history_append"](value, np.uint64(key))
        return value

    def test_order_independent_and_duplicate_sensitive(self):
        keys = [11, 22, 11, 2**63 + 9]
        signatures = {int(self.signature(order)) for order in itertools.permutations(keys)}
        self.assertEqual(len(signatures), 1)
        self.assertNotEqual(self.signature([11, 11, 22]), self.signature([11, 22, 22]))
        self.assertNotEqual(self.signature([11, 11]), self.signature([]))
        self.assertNotEqual(self.signature([11]), self.signature([11, 11]))

    def test_context_score_isolation_but_legal_ordering_hint_survives(self):
        c = self.c
        keys = np.zeros(80, np.uint64)
        moves = np.zeros(80, np.int32)
        scores = np.zeros(64, np.int16)
        depths = np.zeros(64, np.uint8)
        flags = np.zeros(64, np.uint8)
        age = np.ones(1, np.int32)
        key = np.uint64(0x1234567812345678)
        context_a = c["score_tt_key"](key, 5, 200, self.signature([11, 22, 11]))
        context_reordered = c["score_tt_key"](key, 5, 200, self.signature([22, 11, 11]))
        c["tt_store"](context_a, 123, 9, 0, 777, 0, keys, moves, scores, depths, flags, age)
        c["move_hint_store"](key, 123, keys, moves)
        self.assertTrue(c["tt_probe"](context_reordered, 0, keys, moves, scores, depths, flags)[0])
        for fifty, cap, bag in ((6, 200, [11, 22, 11]), (5, 199, [11, 22, 11]), (5, 200, [11, 22, 22])):
            changed = c["score_tt_key"](key, fifty, cap, self.signature(bag))
            self.assertFalse(c["tt_probe"](changed, 0, keys, moves, scores, depths, flags)[0])
            self.assertEqual(c["move_hint_probe"](key, keys, moves), 123)
        # A hint-table index collision must miss when the full board key differs.
        collision = key + np.uint64(16)
        c["move_hint_store"](collision, 456, keys, moves)
        self.assertEqual(c["move_hint_probe"](key, keys, moves), 0)
        self.assertEqual(c["move_hint_probe"](collision, keys, moves), 456)
        # Historical test allocators without the optional hint tail stay safe.
        self.assertEqual(c["move_hint_probe"](key, keys[:64], moves[:64]), 0)

    def test_different_count_bags_do_not_alias_in_fixed_random_sample(self):
        rng = random.Random(2026090502)
        observed = {}
        for _ in range(500):
            keys = [rng.getrandbits(64) for _ in range(rng.randrange(1, 35))]
            keys += keys[:rng.randrange(0, min(5, len(keys)))]
            signature = int(self.signature(keys))
            bag = tuple(sorted(Counter(keys).items()))
            if signature in observed:
                self.assertEqual(bag, observed[signature])
            observed[signature] = bag


class ReversibleWindowTests(unittest.TestCase):
    def tearDown(self):
        history.reset()

    def test_root_slice_retains_exactly_known_reversible_predecessors(self):
        keys = [10, 20, 10, 20, 30, 40, 50]
        self.assertEqual(history.reversible_root_keys(keys, 0), [])
        self.assertEqual(history.reversible_root_keys(keys, 2), [30, 40])
        self.assertEqual(history.reversible_root_keys(keys, 99), keys[:-1])
        self.assertEqual(history.reversible_root_keys([], 99), [])

    def test_recorded_pair_disappears_after_own_and_opponent_pawn_move(self):
        board = chess.Board()
        history.observe_served(board)
        for ours, theirs in (("g1f3", "g8f6"), ("f3g1", "f6g8")):
            history.observe_our_uci(board, ours)
            board.push_uci(ours)
            board.push_uci(theirs)
            history.observe_served(board)
        self.assertEqual(len(history.zkeys()), 5)
        self.assertEqual(history.zkeys().count(board_nb.from_fen(board.fen()).key), 2)
        history.observe_our_uci(board, "e2e4")
        board.push_uci("e2e4")
        self.assertEqual(history.zkeys(), [board_nb.from_fen(board.fen()).key])
        board.push_uci("e7e5")
        history.observe_served(board)
        self.assertEqual(history.zkeys(), [board_nb.from_fen(board.fen()).key])

    def test_zeroing_native_entry_rebases_without_overwriting_parent(self):
        c = source_functions(HELPERS + ("qsearch_nb", "negamax_nb"), dict(
            MAX_PLY=96, DRAW=0, MATE=32000, INF=32001, FIFTY=6, KEY=8, SIDE=3, OCC=2,
            EXACT=0, LOWER=1, UPPER=2, CHECK_EXT_PLY=48, STALEMATE_SCAN_MAX_PIECES=8,
            check_clock=lambda *a: False, in_check_nb=lambda *a: False,
            insufficient_material_nb=lambda *a: False, popc=lambda v: 20,
            evaluate_nb=lambda *a: 37, gen_noisy=lambda *a: 0, sort_moves=lambda *a: None))
        state = np.zeros(12, np.uint64)
        state[8] = 777
        parent = np.zeros(110, np.uint64)
        parent[:4] = [11, 22, 11, 22]
        seen = []
        def count(key, hist, hlen):
            seen.append((hlen, hist.ctypes.data - parent.ctypes.data))
            return 0
        c["count_key"] = count
        common = dict(bb=np.zeros(12, np.uint64), mb=np.zeros(64, np.int8), st=state,
                      alpha=-1000, beta=1000, ply=1, hist=parent, hlen=4,
                      adjudicate=True, cap_left=599, has_pair=True, hist_sig=np.uint64(555),
                      max_nodes=10000, allow_abort=False, undos=np.zeros((96,7),np.uint64),
                      stacks=np.zeros((96,256),np.int32), scratches=np.zeros((96,256),np.int32),
                      ttk=np.zeros(80,np.uint64), ttm=np.zeros(80,np.int32), tts=np.zeros(64,np.int16),
                      ttd=np.zeros(64,np.uint8), ttg=np.zeros(64,np.uint8), tta=np.ones(1,np.int32),
                      killers=np.zeros((96,2),np.int32), histy=np.zeros((12,64),np.int32),
                      nodes=np.zeros(2,np.int64), aborted=np.zeros(1,np.int32))
        with np.errstate(over="ignore"):
            self.assertEqual(c["qsearch_nb"](**common), 37)
            self.assertEqual(c["negamax_nb"](**common, depth=0), 37)
        self.assertTrue(seen)
        self.assertTrue(all(length == 0 and offset == 32 for length, offset in seen))
        np.testing.assert_array_equal(parent[:4], [11,22,11,22])
        self.assertEqual(parent[4], 777)

    def test_legal_null_triangulation_is_not_a_real_claim(self):
        board = chess.Board("3q3k/8/8/8/8/8/8/K2Q4 b - - 0 1")
        keys = [board_nb.from_fen(board.fen()).key]
        for uci in ("h8g8", "a1b1", "g8g7", "b1a1", "g7h8", "a1b1", "h8g8",
                    "b1b2", "g8h8", "b2a1", "h8h7", "a1a2", "h7g8", "a2a1", "g8h8"):
            board.push_uci(uci)
            self.assertTrue(board.is_valid())
            self.assertIsNone(board.outcome(claim_draw=True))
            keys.append(board_nb.from_fen(board.fen()).key)
        self.assertFalse(board.can_claim_threefold_repetition())
        board.push(chess.Move.null())
        fake_key = board_nb.from_fen(board.fen()).key
        self.assertEqual(keys[:-1].count(fake_key), 2)
        # Confirms why the unchanged real-history test would be a false draw;
        # the compact actual-null-call gate below removes it.
        self.assertTrue(search_nb._is_repeat(fake_key, keys[:-1]))

    def test_real_claim_equivalence_before_and_after_zeroing(self):
        board = chess.Board()
        all_keys = [board_nb.from_fen(board.fen()).key]
        positions = []
        for uci in ("g1f3", "g8f6", "f3g1", "f6g8", "e2e4", "e7e5",
                    "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"):
            board.push_uci(uci)
            all_keys.append(board_nb.from_fen(board.fen()).key)
            positions.append((board.copy(stack=True), list(all_keys)))
        for current, keys in positions:
            pos = board_nb.from_fen(current.fen())
            full = keys[:-1]
            trimmed = history.reversible_root_keys(keys, pos.fifty)
            legal = movegen_nb.generate_legal(pos)
            expected = current.can_claim_threefold_repetition()
            for prior in (full, trimmed):
                actual = search_nb._is_repeat(pos.key, prior) or search_nb._threefold_claim_from_legal(pos, prior, legal)
                self.assertEqual(actual, expected, current.fen())
            self.assertEqual(search_nb._has_repetition_pair(trimmed, pos.key),
                             len(set(trimmed + [pos.key])) != len(trimmed) + 1)

    def test_actual_fallback_search_matches_full_history_after_zeroing(self):
        # The old repeated bag is unreachable after a pawn/capture. Actual
        # native-shaped source paths and fallback both have to discard it.
        search_nb._adjudicate = True
        search_nb._allow_abort = False
        for fen in ("7k/6p1/8/8/8/8/P7/KR6 w - - 0 12",
                    "7k/6p1/8/8/8/8/P7/KR6 b - - 0 12"):
            pos = board_nb.from_fen(fen)
            bad_old = [pos.key, pos.key, 123, 123]
            actual = search_nb._negamax(pos, 1, -32001, 32001, 0, bad_old, 575)
            empty = search_nb._negamax(pos, 1, -32001, 32001, 0, [], 575)
            self.assertEqual(actual, empty)
            self.assertNotEqual(actual, 0)
            self.assertEqual(bad_old, [pos.key, pos.key, 123, 123])


class CompactNullBarrierTests(unittest.TestCase):
    def test_real_and_virtual_contexts_are_separate_until_zeroing(self):
        c = source_functions(HELPERS)
        with np.errstate(over="ignore"):
            real = c["history_append"](c["HIST_SEED"], np.uint64(111))
            virtual = c["history_append"](c["NULL_HIST_SEED"], np.uint64(111))
            self.assertNotEqual(real, virtual)
            self.assertNotEqual(c["score_tt_key"](111, 15, 200, real),
                                c["score_tt_key"](111, 15, 200, virtual))
        # A genuine zeroing child begins with no reachable prior board in
        # either game. The shared future rule state is therefore identical.
        self.assertEqual(history.reversible_root_keys([11,22,11,333], 0), [])
        self.assertEqual(history.reversible_root_keys([77,88,77,333], 0), [])

    def test_actual_null_call_clears_real_or_nested_virtual_ledger(self):
        c = source_functions(HELPERS + ("negamax_nb",), dict(
            MAX_PLY=96, DRAW=0, MATE=32000, INF=32001, FIFTY=6, KEY=8, SIDE=3,
            EXACT=0, LOWER=1, UPPER=2, U_CAP=0, CHECK_EXT_PLY=48,
            RFP_MAX_D=6, RFP_MARGIN=80, NMP_MIN_D=3,
            check_clock=lambda *args: False, in_check_nb=lambda *args: False,
            insufficient_material_nb=lambda *args: False,
            evaluate_nb=lambda *args: 150, has_nm_pieces=lambda *args: True,
            nmp_safe_nb=lambda *args: True, gen_legal=lambda *args: 20,
            fifty_claim_nb=lambda *args: False, intended_threefold_claim_nb=lambda *args: False))
        actual = c["negamax_nb"]
        names = inspect.signature(actual).parameters
        for seed in (c["HIST_SEED"], c["NULL_HIST_SEED"]):
            parent = np.zeros(112, np.uint64)
            parent[:4] = [11,22,11,22]
            state = np.zeros(12,np.uint64)
            state[8] = 777
            state[6] = 15
            before = state.copy()
            calls = []
            def child(*args):
                values = dict(zip(names, args))
                self.assertEqual(values["hlen"], 0)
                self.assertFalse(values["has_pair"])
                self.assertEqual(values["hist_sig"], c["NULL_HIST_SEED"])
                self.assertEqual(values["hist"].ctypes.data - parent.ctypes.data, 32)
                self.assertEqual(values["cap_left"], 200)
                self.assertEqual(values["st"][6], 15)
                # Future virtual keys may use only this unused suffix.
                values["hist"][0] = 999
                calls.append(True)
                return -100
            c["negamax_nb"] = child
            c["make_null"] = lambda bb, mb, st, undo: st.__setitem__(3, 1)
            c["unmake_null"] = lambda st, undo: st.__setitem__(slice(None), before)
            values = dict(bb=np.zeros(12,np.uint64), mb=np.zeros(64,np.int8), st=state,
                          depth=7, alpha=99, beta=100, ply=0, hist=parent, hlen=4,
                          adjudicate=False, cap_left=200, has_pair=True, hist_sig=seed,
                          max_nodes=1000, allow_abort=False, undos=np.zeros((96,7),np.uint64),
                          stacks=np.zeros((96,256),np.int32), scratches=np.zeros((96,256),np.int32),
                          ttk=np.zeros(80,np.uint64), ttm=np.zeros(80,np.int32),
                          tts=np.zeros(64,np.int16), ttd=np.zeros(64,np.uint8),
                          ttg=np.zeros(64,np.uint8), tta=np.ones(1,np.int32),
                          killers=np.zeros((96,2),np.int32), histy=np.zeros((12,64),np.int32),
                          nodes=np.zeros(2,np.int64), aborted=np.zeros(1,np.int32))
            with np.errstate(over="ignore"):
                self.assertEqual(actual(**values), 100)
            self.assertEqual(calls, [True])
            np.testing.assert_array_equal(parent[:4], [11,22,11,22])
            np.testing.assert_array_equal(state, before)
            self.assertEqual(parent[4], 999)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "mode": "Actual source bodies and real Python fallback; no Numba compilation.",
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob("*.py")}}
    (Path(__file__).parent / "history-lightweight-gate.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
