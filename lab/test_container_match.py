"""Docker-free unit tests for the competition-shaped match orchestrator."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from lab.container_match import (
    CONTAINER_MEMORY,
    EXPECTED_MEMORY_BYTES,
    EXPECTED_PIDS,
    EXPECTED_TMP_BYTES,
    GamePlan,
    build_game_plan,
    controller_runtime,
    docker_command,
    parse_cpu_pair,
    raw_score_summary,
    snapshot_archive,
    source_provenance,
    validate_probe_payload,
    validate_selected_fens,
    verify_image_provenance,
    verify_snapshot,
)


class ContainerMatchTests(unittest.TestCase):
    def test_pair_swaps_candidate_colour_and_core(self) -> None:
        plans = build_game_plan(("fen-0", "fen-1", "fen-2"), 2, 1, (4, 7))
        self.assertEqual(plans[0].opening_index, 1)
        self.assertEqual(plans[1].opening_index, 1)
        self.assertEqual((plans[0].white_role, plans[0].black_role), ("candidate", "baseline"))
        self.assertEqual((plans[1].white_role, plans[1].black_role), ("baseline", "candidate"))
        self.assertEqual((plans[0].white_cpu, plans[0].black_cpu), (4, 7))
        self.assertEqual((plans[1].white_cpu, plans[1].black_cpu), (4, 7))
        candidate_cores = (plans[0].white_cpu, plans[1].black_cpu)
        self.assertEqual(candidate_cores, (4, 7))
        self.assertEqual(plans[2].opening_index, 2)

    def test_held_out_slice_does_not_wrap(self) -> None:
        with self.assertRaises(ValueError):
            build_game_plan(("fen-0", "fen-1"), 2, 1, (0, 1))

    def test_docker_command_has_runtime_envelope(self) -> None:
        command = docker_command("docker", "image:sha", 3, "safe-name")
        joined = " ".join(command)
        self.assertIn("--cpuset-cpus 3", joined)
        self.assertIn("--cpus 1", joined)
        self.assertIn(f"--memory {CONTAINER_MEMORY}", joined)
        self.assertIn(f"--memory-swap {CONTAINER_MEMORY}", joined)
        self.assertIn("--network none", joined)
        self.assertIn("--read-only", command)
        self.assertIn("--pids-limit 128", joined)
        self.assertIn("HOME=/tmp", command)
        self.assertEqual(command[-1], "image:sha")

    def test_cpu_pair_parser(self) -> None:
        self.assertEqual(parse_cpu_pair("2,5"), (2, 5))
        with self.assertRaises(Exception):
            parse_cpu_pair("2,2")

    def test_archive_tag_is_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "agent.zip"
            with zipfile.ZipFile(archive, "w") as packed:
                packed.writestr("agent.py", "def get_move(fen, time_left_ms): return 'a2a3'\n")
            identity = snapshot_archive(archive, "candidate", root / "snapshots")
            self.assertEqual(len(identity.sha256), 64)
            self.assertTrue(identity.image_tag.endswith(identity.sha256[:16]))
            # The build input stays fixed even if the user-facing path changes.
            archive.write_bytes(b"not the snapshotted zip")
            verify_snapshot(identity)
            self.assertNotEqual(identity.sha256, hashlib.sha256(archive.read_bytes()).hexdigest())
            identity.snapshot_path.write_bytes(b"tampered snapshot")
            with self.assertRaises(SystemExit):
                verify_snapshot(identity)

    def test_controller_runtime_is_exact(self) -> None:
        with self.assertRaises(SystemExit):
            controller_runtime((3, 13), "1.11.2")
        with self.assertRaises(SystemExit):
            controller_runtime((3, 12), "1.11.1")

    def test_selected_fens_are_validated(self) -> None:
        valid = "8/8/8/8/8/4k3/8/4K2R w - - 0 1"
        plan = GamePlan(1, 1, 100, valid, "candidate", "baseline", 0, 1)
        result = validate_selected_fens((plan,))
        self.assertTrue(result["all_valid_nonterminal"])
        invalid = GamePlan(1, 1, 100, "not a fen", "candidate", "baseline", 0, 1)
        with self.assertRaises(SystemExit):
            validate_selected_fens((invalid,))

    def test_probe_requires_hot_path_and_envelope(self) -> None:
        payload = {
            "python": "3.12.11",
            "chess": "1.11.2",
            "numpy": "2.5.2",
            "numba": "0.67.0",
            "machine": "x86_64",
            "core_nb_NUMBA_READY": True,
            "core_nb_WARMUP_S": 39.0,
            "agent_import_s": 40.0,
            "sched_affinity": [3],
            "root_read_only": True,
            "tmp_writable": True,
            "tmp_total_bytes": EXPECTED_TMP_BYTES,
            "network_interfaces": ["lo"],
            "cgroup": {
                "version": 2,
                "cpu_max": "100000 100000",
                "cpuset_cpus_effective": "3",
                "memory_max": str(EXPECTED_MEMORY_BYTES),
                "memory_swap_max": "0",
                "pids_max": str(EXPECTED_PIDS),
            },
        }
        self.assertEqual(validate_probe_payload(payload, 3), [])
        payload["core_nb_NUMBA_READY"] = False
        self.assertIn("core_nb.NUMBA_READY is not true", validate_probe_payload(payload, 3))
        payload["core_nb_NUMBA_READY"] = True
        payload["core_nb_WARMUP_S"] = 50.0
        self.assertTrue(
            any("WARMUP_S" in error for error in validate_probe_payload(payload, 3))
        )
        payload["core_nb_WARMUP_S"] = 39.0
        payload["cgroup"]["memory_max"] = "max"
        self.assertTrue(
            any("memory.max" in error for error in validate_probe_payload(payload, 3))
        )
        payload["cgroup"]["memory_max"] = str(EXPECTED_MEMORY_BYTES)
        payload["network_interfaces"] = ["eth0", "lo"]
        self.assertTrue(
            any("network interfaces" in error for error in validate_probe_payload(payload, 3))
        )

    def test_raw_score_excludes_void_games(self) -> None:
        scored, voids, score = raw_score_summary(1, 1, 0, 3)
        self.assertEqual((scored, voids), (2, 1))
        self.assertEqual(score, 0.75)

    def test_provenance_covers_controller_and_harness(self) -> None:
        provenance = source_provenance(Path(__file__).resolve().parent.parent)
        hashes = provenance["files_sha256"]
        self.assertIn("harness/runner.py", hashes)
        self.assertIn("harness/referee.py", hashes)
        self.assertIn("harness/sandbox.py", hashes)
        self.assertIn("harness/rules.py", hashes)
        self.assertIn("lab/docker/MatchAgent.Dockerfile", hashes)
        self.assertIn("lab/container_match.py", hashes)
        self.assertTrue(provenance["starter_commit"])
        image = {
            "runner_sha256": hashes["harness/runner.py"],
            "probe_sha256": hashes["lab/docker/match_image_probe.py"],
            "dockerfile_sha256": hashes["lab/docker/MatchAgent.Dockerfile"],
        }
        verify_image_provenance((image,), provenance)
        image["runner_sha256"] = "changed"
        with self.assertRaises(SystemExit):
            verify_image_provenance((image,), provenance)


if __name__ == "__main__":
    unittest.main()
