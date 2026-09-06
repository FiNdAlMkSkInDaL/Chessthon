"""Portable command/envelope/integrity tests; never starts systemd or an engine."""
from dataclasses import asdict
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import chess
from harness.sandbox import Agent, AgentFailure, RUNNER
from lab.paired_match_stats import analyze_rows
from lab.storm.linux_match import (
    MEMORY_LIMIT_BYTES, THREAD_ENV, TimedAgent, build_game_plan, cleanup_owned_tree,
    envelope_problems, extraction_problems, make_readonly, parse_telemetry,
    runner_command, safe_extract, snapshot_archive, verify_snapshot,
)


def valid_properties():
    return {'MainPID': '1234', 'MemoryMax': str(MEMORY_LIMIT_BYTES),
            'MemorySwapMax': '0', 'RestrictAddressFamilies': 'AF_UNIX',
            'CPUQuotaPerSecUSec': '1s', 'RuntimeMaxUSec': '10min', 'TasksMax': '128',
            'NoNewPrivileges': 'yes', 'LimitFSIZE': '268435456'}


class LinuxMatchTests(unittest.TestCase):
    def test_exact_official_runner_and_requested_service_envelope(self):
        directory = Path('/tmp/a directory/agent')
        home = Path('/tmp/a directory/home')
        command = runner_command(directory, home, 2, 'chesstk-a-1-white.service', '/python312')
        for argument in ('--user', '--quiet', '--wait', '--pipe', '--collect',
                         '--property=CPUAffinity=2', '--property=CPUQuota=100%',
                         '--property=MemoryMax=2147483648', '--property=MemorySwapMax=0',
                         '--property=RestrictAddressFamilies=AF_UNIX', '--property=RuntimeMaxSec=600',
                         '--property=TasksMax=128', '--property=NoNewPrivileges=yes',
                         '--property=LimitFSIZE=268435456',
                         '--property=KillMode=control-group'):
            self.assertIn(argument, command)
        self.assertEqual(command[-6:], ['2', '/python312', '-B', '-u', str(RUNNER), str(directory)])
        self.assertNotIn('laptop_runner.py', ' '.join(command))
        self.assertNotIn('shell', command)
        for variable in THREAD_ENV:
            self.assertIn('--setenv='+variable+'=1', command)
        self.assertIn('--setenv=HOME='+str(home), command)
        with self.assertRaises(ValueError):
            runner_command(directory, home, 2, 'bad/unit')

    def test_envelope_requires_actual_affinity_and_all_limits(self):
        self.assertEqual(envelope_problems(valid_properties(), 2, [2]), [])
        for key in ('MemoryMax', 'MemorySwapMax', 'RestrictAddressFamilies',
                    'CPUQuotaPerSecUSec', 'RuntimeMaxUSec', 'TasksMax', 'NoNewPrivileges', 'LimitFSIZE'):
            broken = valid_properties()
            broken.pop(key)
            self.assertTrue(envelope_problems(broken, 2, [2]), key)
        self.assertTrue(envelope_problems(valid_properties(), 2, [1, 2]))
        self.assertTrue(envelope_problems(valid_properties(), 2, None))

    def test_stops_service_before_official_relay_and_is_idempotent(self):
        agent = TimedAgent(Path('/agent'), Path('/home'), 0, 'chesstk-a.service', 'candidate')
        operations = []
        with patch.object(agent, '_sample', return_value={}), \
             patch('lab.storm.linux_match.stop_service', side_effect=lambda unit: operations.append('service')), \
             patch.object(Agent, 'stop', side_effect=lambda: operations.append('relay')):
            agent.stop()
            agent.stop()
        self.assertEqual(operations, ['service', 'relay'])

    def test_cleanup_failure_still_drains_official_agent(self):
        agent = TimedAgent(Path('/agent'), Path('/home'), 0, 'chesstk-a.service', 'candidate')
        with patch.object(agent, '_sample', return_value={}), \
             patch('lab.storm.linux_match.stop_service', side_effect=OSError('blocked')), \
             patch.object(Agent, 'stop') as stop:
            agent.stop()
        stop.assert_called_once()
        self.assertIn('blocked', agent.cleanup_error)

    def test_start_rejects_unenforced_limits_without_readiness_override(self):
        agent = TimedAgent(Path('/agent'), Path('/home'), 0, 'chesstk-a.service', 'candidate')
        with patch.object(Agent, 'start'), patch.object(agent, '_sample', return_value={}), \
             patch('os.sched_getaffinity', return_value={0}, create=True):
            with self.assertRaises(AgentFailure):
                agent.start(90)
        self.assertTrue(agent.envelope_errors)
        self.assertIsNotNone(agent.init_s)

    def test_snapshot_is_immutable_fresh_readonly_and_cleanup_is_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            owner = Path(temporary)
            source = owner/'source.zip'
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('agent.py', 'def get_move(fen, time_left_ms): return "e2e4"\n')
            snapshot = snapshot_archive(source, 'candidate', owner/'snapshots')
            first, second = owner/'first', owner/'second'
            safe_extract(snapshot, first)
            make_readonly(first)
            source.write_bytes(b'source path drift does not alter snapshot')
            verify_snapshot(snapshot)
            safe_extract(snapshot, second)
            self.assertEqual(extraction_problems(snapshot, first), [])
            self.assertEqual((first/'agent.py').read_bytes(), (second/'agent.py').read_bytes())
            if os.name != 'nt':
                self.assertEqual(first.stat().st_mode & 0o777, 0o555)
                self.assertEqual((first/'agent.py').stat().st_mode & 0o777, 0o444)
            with self.assertRaises(ValueError):
                cleanup_owned_tree(owner, owner)
            cleanup_owned_tree(first, owner)
            self.assertFalse(first.exists())
            self.assertTrue(second.exists())

    def test_colour_pair_uses_same_cpu_and_stats_schema(self):
        plans = build_game_plan((chess.STARTING_FEN,), 1, 0, (2, 2))
        records = []
        for plan in plans:
            self.assertEqual((plan.white_cpu, plan.black_cpu), (2, 2))
            records.append({'type': 'game', 'run_id': 'test', **asdict(plan),
                            'result': 'draw', 'termination': 'threefold_repetition',
                            'candidate_points': .5, 'candidate_failure': False,
                            'baseline_failure': False,
                            'white_sha256': plan.white_role, 'black_sha256': plan.black_role})
        stats = analyze_rows(records, min_pairs=1, bootstrap_samples=100)
        self.assertEqual(stats['included_pairs'], 1)
        self.assertEqual(stats['validation_errors'], [])

    def test_s4_telemetry_accepts_negative_score_and_ignores_noise(self):
        rows = parse_telemetry('noise\nS4 p42 d7 n12345 s-165 t4012 b4220\n')
        self.assertEqual(rows, [{'game_ply': 42, 'depth': 7, 'nodes': 12345,
                                 'score': -165, 'elapsed_ms': 4012, 'target_ms': 4220}])


if __name__ == '__main__':
    unittest.main()
