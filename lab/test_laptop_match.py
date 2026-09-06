"""Unit and protocol-smoke tests for the Windows laptop match harness."""

from __future__ import annotations

import json
import os
import tempfile
import types
import unittest
import zipfile
from pathlib import Path

import chess

from harness.sandbox import Agent
from lab.laptop_match import (
    MEMORY_LIMIT_BYTES,
    build_game_plan,
    extraction_problems,
    parse_cpu_pair,
    parse_runner_diagnostics,
    runner_command,
    runner_diagnostic_problems,
    safe_extract,
    snapshot_archive,
    verify_snapshot,
    windows_available_cpus,
)
from lab.laptop_runner import numba_readiness_evidence
from lab.paired_match_stats import analyze_rows


class _Dispatcher:
    def __init__(self, *, compiled: bool = True) -> None:
        self.nopython_signatures = ["sig"] if compiled else []
        self.signatures = ["sig"] if compiled else []


def _fake_core(*, ready: bool, compiled: bool = True, warmup_s: float = 51.0) -> types.ModuleType:
    core = types.ModuleType("core_nb")
    core.HAS_NUMBA = True
    core.NUMBA_READY = ready
    core.WARMUP_S = warmup_s
    core.perft_nb = _Dispatcher(compiled=compiled)
    core.root_search_nb = _Dispatcher(compiled=compiled)
    return core


class LaptopMatchTests(unittest.TestCase):
    def test_pair_swaps_candidate_colour_and_logical_cpu(self) -> None:
        plans = build_game_plan(("fen0", "fen1", "fen2"), 2, 1, (3, 8))
        self.assertEqual((plans[0].white_role, plans[0].black_role), ("candidate", "baseline"))
        self.assertEqual((plans[1].white_role, plans[1].black_role), ("baseline", "candidate"))
        self.assertEqual((plans[0].white_cpu, plans[0].black_cpu), (3, 8))
        self.assertEqual((plans[1].white_cpu, plans[1].black_cpu), (3, 8))
        self.assertEqual((plans[0].white_cpu, plans[1].black_cpu), (3, 8))
        self.assertEqual(plans[0].fen, plans[1].fen)
        self.assertEqual(plans[0].opening_index, plans[1].opening_index)

    def test_cpu_parser(self) -> None:
        self.assertEqual(parse_cpu_pair("2,7"), (2, 7))
        with self.assertRaises(Exception):
            parse_cpu_pair("2,2")

    def test_snapshot_and_clean_extraction_are_content_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "source.zip"
            with zipfile.ZipFile(archive, "w") as packed:
                packed.writestr(
                    "agent.py", "def get_move(fen, time_left_ms): return 'e2e4'\n"
                )
            snapshot = snapshot_archive(archive, "candidate", root / "snapshots")
            extracted = root / "agent"
            safe_extract(snapshot, extracted)
            self.assertEqual(extraction_problems(snapshot, extracted), [])
            (extracted / "extra.txt").write_text("drift", encoding="utf-8")
            self.assertTrue(any("extra" in item for item in extraction_problems(snapshot, extracted)))
            archive.write_bytes(b"changed source does not affect the snapshot")
            verify_snapshot(snapshot)
            snapshot.snapshot_path.write_bytes(b"tampered")
            with self.assertRaises(SystemExit):
                verify_snapshot(snapshot)

    def test_readiness_override_requires_completed_compilation(self) -> None:
        core = _fake_core(ready=False, warmup_s=51.0)
        evidence = numba_readiness_evidence(core)
        self.assertTrue(evidence["compiled"])
        self.assertTrue(evidence["override_applied"])
        self.assertTrue(core.NUMBA_READY)

        for broken in (
            _fake_core(ready=False, compiled=False, warmup_s=51.0),
            _fake_core(ready=False, compiled=True, warmup_s=0.0),
            _fake_core(ready=False, compiled=True, warmup_s=float("nan")),
        ):
            evidence = numba_readiness_evidence(broken)
            self.assertFalse(evidence["compiled"])
            self.assertFalse(evidence["override_applied"])
            self.assertFalse(broken.NUMBA_READY)

    def test_match_rejects_fallback_or_unenforced_diagnostic(self) -> None:
        valid = {
            "envelope": {
                "affinity": {"applied": True, "requested_cpu": 3, "effective_mask": 8},
                "memory_job": {"applied": True, "limit_bytes": MEMORY_LIMIT_BYTES},
            },
            "numba": {"compiled": True, "effective_ready": True},
            "thread_env": {
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "NUMBA_NUM_THREADS": "1",
                "NUMEXPR_NUM_THREADS": "1",
                "VECLIB_MAXIMUM_THREADS": "1",
                "BLIS_NUM_THREADS": "1",
            },
        }
        self.assertEqual(runner_diagnostic_problems([valid], expected_cpu=3), [])
        fallback = json.loads(json.dumps(valid))
        fallback["numba"]["effective_ready"] = False
        self.assertTrue(
            any(
                "fallback" in item
                for item in runner_diagnostic_problems([fallback], expected_cpu=3)
            )
        )
        cold = json.loads(json.dumps(valid))
        cold["numba"]["compiled"] = False
        self.assertTrue(
            any(
                "nopython" in item
                for item in runner_diagnostic_problems([cold], expected_cpu=3)
            )
        )
        unbounded = json.loads(json.dumps(valid))
        unbounded["envelope"]["memory_job"]["applied"] = False
        self.assertTrue(
            any(
                "Job Object" in item
                for item in runner_diagnostic_problems([unbounded], expected_cpu=3)
            )
        )
        wrong_cpu = json.loads(json.dumps(valid))
        wrong_cpu["envelope"]["affinity"]["effective_mask"] = 16
        self.assertTrue(runner_diagnostic_problems([wrong_cpu], expected_cpu=3))
        wrong_threads = json.loads(json.dumps(valid))
        wrong_threads["thread_env"]["NUMBA_NUM_THREADS"] = "2"
        self.assertTrue(runner_diagnostic_problems([wrong_threads], expected_cpu=3))

    def test_command_is_cold_isolated_and_strict(self) -> None:
        command = runner_command(Path("agent"), Path("empty-home"), 4, MEMORY_LIMIT_BYTES)
        joined = " ".join(command)
        self.assertIn("-B", command)
        self.assertIn("--cpu 4", joined)
        self.assertIn(f"--memory-limit-bytes {MEMORY_LIMIT_BYTES}", joined)
        self.assertIn("--strict-envelope", command)
        self.assertIn("empty-home", joined)

    def test_game_rows_are_paired_stats_compatible(self) -> None:
        fen = chess.STARTING_FEN
        candidate = "c" * 64
        baseline = "b" * 64
        rows = [
            {
                "type": "game",
                "run_id": "run",
                "pair": 1,
                "opening_index": 100,
                "fen": fen,
                "candidate_colour": "white",
                "white_sha256": candidate,
                "black_sha256": baseline,
                "result": "white",
                "termination": "checkmate",
                "candidate_points": 1.0,
                "candidate_failure": False,
                "baseline_failure": False,
            },
            {
                "type": "game",
                "run_id": "run",
                "pair": 1,
                "opening_index": 100,
                "fen": fen,
                "candidate_colour": "black",
                "white_sha256": baseline,
                "black_sha256": candidate,
                "result": "black",
                "termination": "checkmate",
                "candidate_points": 1.0,
                "candidate_failure": False,
                "baseline_failure": False,
            },
        ]
        stats = analyze_rows(rows, min_pairs=1, bootstrap_samples=100)
        self.assertEqual(stats["validation_errors"], [])
        self.assertEqual(stats["included_pairs"], 1)
        self.assertEqual(stats["wins"], 2)

    @unittest.skipUnless(os.name == "nt", "Windows resource-envelope smoke")
    def test_runner_protocol_smoke_is_cpu_pinned_and_memory_limited(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            agent_dir = root / "agent"
            agent_dir.mkdir()
            (agent_dir / "agent.py").write_text(
                "def get_move(fen, time_left_ms):\n    return 'e2e4'\n",
                encoding="utf-8",
            )
            cpu = windows_available_cpus()[0]
            agent = Agent(runner_command(agent_dir, root / "home", cpu, MEMORY_LIMIT_BYTES))
            try:
                agent.start(10.0)
                self.assertEqual(agent.move(chess.STARTING_FEN, 1000), "e2e4")
            finally:
                agent.stop()
            diagnostics = parse_runner_diagnostics(agent.stderr_tail)
            self.assertEqual(len(diagnostics), 1)
            envelope = diagnostics[0]["envelope"]
            self.assertTrue(envelope["affinity"]["applied"])
            self.assertEqual(envelope["affinity"]["effective_mask"], 1 << cpu)
            self.assertTrue(envelope["memory_job"]["applied"])
            self.assertFalse(diagnostics[0]["numba"]["module_loaded"])
            self.assertFalse((agent_dir / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
