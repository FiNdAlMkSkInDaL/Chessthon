"""Run directly in an isolated process; no Numba import or compilation.

Native tests of the same control bytes are still required on the signer.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys
import time
import unittest
import zipfile

import chess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "storm_rules600_release_control"
sys.path.insert(0, str(SOURCE))
import board_nb
import history
import movegen_nb
import search_nb


def function_dump(source, name):
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.dump(node, include_attributes=False)


class MinimalControlTests(unittest.TestCase):
    def test_original_chess_features_are_preserved(self):
        with zipfile.ZipFile(ROOT / "dist/agent-storm-v4-linux-x86.zip") as archive:
            for name in ("agent.py", "bitops_nb.py", "board_nb.py", "movegen_nb.py", "tables_nb.py", "tt_nb.py"):
                self.assertEqual((SOURCE / name).read_bytes(), archive.read(name), name)
            for name, functions in (
                ("core_nb.py", ("see_nb", "quiet_reduction", "history_update", "is_repeat", "pesto_nb")),
                ("search_nb.py", ("see", "_is_repeat")),
                ("history.py", ("filter_root_moves", "is_winning", "_auto_claim_now", "_opponent_can_force_auto_claim")),
            ):
                original = archive.read(name).decode("utf-8-sig")
                current = (SOURCE / name).read_text(encoding="utf-8-sig")
                for function in functions:
                    self.assertEqual(function_dump(original, function), function_dump(current, function), function)
            for name in ("storm_clock.py", "time_nb.py"):
                original = archive.read(name).decode("utf-8-sig").replace("\r\n", "\n")
                current = (SOURCE / name).read_text(encoding="utf-8-sig")
                self.assertEqual(original.replace("PLY_CAP = 300", "PLY_CAP = 600"), current)

    def test_history_uses_fen_absolute_ply(self):
        history.reset()
        for fen, expected in (("8/8/8/8/8/k7/2q5/K7 b - - 0 300", 599),
                              (chess.STARTING_FEN, 0)):
            history.observe_served(chess.Board(fen))
            self.assertEqual(history.game_ply(), expected)
            self.assertFalse(history.use_adjudication_eval())

    def test_cap_root_draw_mate_and_maximum_ply(self):
        search_nb._deadline = time.perf_counter() + 5
        search_nb._adjudicate = False
        for fen, mate in (("7k/7p/8/8/8/8/P7/K7 b - - 0 300", False),
                          ("8/8/8/8/8/k7/2q5/K7 b - - 0 300", True)):
            board = chess.Board(fen)
            self.assertTrue(board.is_valid())
            position = board_nb.from_fen(fen)
            before = position.key
            chosen, score = search_nb._root_search(
                position, movegen_nb.generate_legal(position), 1, [], None, -32001, 32001, 1)
            self.assertEqual(position.key, before)
            if mate:
                board.push_uci(movegen_nb.move_uci(chosen))
                self.assertTrue(board.is_checkmate())
                self.assertGreaterEqual(score, 31000)
            else:
                self.assertEqual(score, 0)
        terminal = board_nb.from_fen(board.fen())
        self.assertEqual(search_nb._qsearch(terminal, -32001, 32001, 96, [], 0), -32000 + 96)

    def test_cap_tt_identity_only_changes_inside_reachable_cap_horizon(self):
        self.assertEqual(search_nb._cap_tt_key(123, 600), 123)
        self.assertEqual(search_nb._cap_tt_key(123, 97), 123)
        keys = [search_nb._cap_tt_key(123, remaining) for remaining in range(97)]
        self.assertEqual(len(set(keys)), 97)
        self.assertNotIn(123, keys)

    def test_native_cap_arguments_match_real_and_null_edges(self):
        tree = ast.parse((SOURCE / "core_nb.py").read_text())
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for owner in ("negamax_nb", "qsearch_nb", "root_search_nb"):
            for node in ast.walk(functions[owner]):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                if node.func.id not in ("negamax_nb", "qsearch_nb"):
                    continue
                parameters = [arg.arg for arg in functions[node.func.id].args.args]
                history_length = node.args[parameters.index("hlen")]
                expected = "cap_left - 1" if ast.unparse(history_length) == "hlen2" else "cap_left"
                self.assertEqual(ast.unparse(node.args[parameters.index("cap_left")]), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
