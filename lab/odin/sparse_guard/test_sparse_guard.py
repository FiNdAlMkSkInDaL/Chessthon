"""Bounded source-body tests; no Numba import or compilation."""
from __future__ import annotations
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import zipfile

import chess
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "odin_sparse_guard"
BASE = ROOT / "lab/odin/history_perf/odin-history-perf-source.zip"
sys.path.insert(0, str(SOURCE))
from board_nb import from_fen


class ReachedOrdinarySearch(Exception):
    pass


def find_function(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


class SparseGuardTests(unittest.TestCase):
    def test_all_other_modules_and_search_gates_unchanged(self):
        with zipfile.ZipFile(BASE) as archive:
            for name in archive.namelist():
                if name != "core_nb.py":
                    self.assertEqual(archive.read(name), (SOURCE / name).read_bytes(), name)
            baseline = ast.parse(archive.read("core_nb.py").decode("utf-8"))
        candidate = ast.parse((SOURCE / "core_nb.py").read_text(encoding="utf-8"))

        class RemoveOnlyNmpBranch(ast.NodeTransformer):
            def visit_If(self, node):
                if any(isinstance(n, ast.Name) and n.id == "NMP_MIN_D" for n in ast.walk(node.test)):
                    return ast.Pass()
                return self.generic_visit(node)

        # Removing exactly the NMP eligibility/body must make the entire
        # modules identical, including every other selectivity gate and dtype.
        self.assertEqual(ast.dump(RemoveOnlyNmpBranch().visit(baseline), include_attributes=False),
                         ast.dump(RemoveOnlyNmpBranch().visit(candidate), include_attributes=False))

    def _exercise(self, sparse, beta):
        tree = ast.parse((SOURCE / "core_nb.py").read_text(encoding="utf-8"))
        selected = [copy.deepcopy(find_function(tree, name)) for name in ("nmp_safe_nb", "negamax_nb")]
        for function in selected:
            function.decorator_list = []
        names = [arg.arg for arg in selected[-1].args.args]
        fen = ("7k/7p/8/8/8/8/P7/KR6 w - - 5 9" if sparse else
               "3q3k/8/8/8/8/8/8/K2Q4 w - - 5 9")
        self.assertTrue(chess.Board(fen).is_valid())
        position = from_fen(fen)
        env = dict(np=np, MAX_PLY=96, MATE=32000, MATE_WIN=31000,
                   DRAW=0, CHECK_EXT_PLY=48, RFP_MAX_D=6, RFP_MARGIN=80,
                   NMP_MIN_D=3, IIR_MIN_D=4, SIDE=3, KEY=8, FIFTY=6, U_CAP=0,
                   EXACT=0, LOWER=1, UPPER=2,
                   check_clock=lambda *_a: False, in_check_nb=lambda *_a: False,
                   count_key=lambda *_a: 0, insufficient_material_nb=lambda *_a: False,
                   history_append=lambda sig, key: sig, score_tt_key=lambda *_a: np.uint64(1),
                   move_hint_probe=lambda *_a: 0, tt_probe=lambda *_a: (False, 0, 0, 0, 0),
                   evaluate_nb=lambda *_a: beta + 50, has_nm_pieces=lambda *_a: True,
                   popc=lambda value: int(value).bit_count())
        values = {name: 0 for name in names}
        values.update(bb=np.array(position.bb, np.uint64), mb=np.array(position.mb, np.int8),
                      st=np.zeros(12, np.uint64), depth=7, alpha=beta - 1,
                      beta=beta, ply=0, hist=np.zeros(104, np.uint64), hlen=0,
                      adjudicate=False, cap_left=583, has_pair=False, null_tree=False,
                      hist_sig=np.uint64(1), undos=np.zeros((4, 7), np.uint64),
                      stacks=np.zeros((4, 256), np.int32), scratches=np.zeros((4, 256), np.int32),
                      nodes=np.zeros(2, np.int64), aborted=np.zeros(1, np.int32))
        values["st"][8] = position.key
        values["st"][6] = 5
        before = values["st"].copy()
        calls = []

        def make_null(_bb, _mb, state, _undo):
            self.assertFalse(sparse, "a sparse ending must never enter NMP")
            calls.append("make_null")
            state[3] ^= np.uint64(1)

        def unmake_null(state, _undo):
            calls.append("unmake_null")
            state[:] = before

        def child(*args):
            self.assertFalse(sparse)
            call = dict(zip(names, args))
            self.assertTrue(call["null_tree"])
            self.assertEqual(call["cap_left"], 583)
            self.assertEqual((call["alpha"], call["beta"]), (-beta, -beta + 1))
            calls.append("null_child")
            return -beta

        def ordinary(*_args):
            raise ReachedOrdinarySearch

        env.update(make_null=make_null, unmake_null=unmake_null, gen_legal=ordinary)
        exec(compile(ast.Module(body=selected, type_ignores=[]), "<actual-sparse-guard>", "exec"), env)
        self.assertEqual(env["nmp_safe_nb"](values["bb"]), not sparse)
        actual = env["negamax_nb"]
        env["negamax_nb"] = child
        if sparse:
            with self.assertRaises(ReachedOrdinarySearch):
                actual(**values)
            self.assertEqual(calls, [])
        else:
            self.assertEqual(actual(**values), beta)
            self.assertEqual(calls, ["make_null", "null_child", "unmake_null"])
        self.assertTrue(np.array_equal(values["st"], before))

    def test_sparse_position_skips_nmp_and_continues_regular_search(self):
        self._exercise(True, 100)
        self._exercise(True, -100)

    def test_rich_position_retains_nmp_and_exact_restoration(self):
        self._exercise(False, 100)
        self._exercise(False, -100)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SparseGuardTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"passed": result.wasSuccessful(), "tests": result.testsRun,
              "native_compilation": False,
              "core_sha256": hashlib.sha256((SOURCE / "core_nb.py").read_bytes()).hexdigest()}
    (Path(__file__).resolve().parent / "lightweight-gate.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
