"""Native Odin colour-paired ZIP matches through an explicitly pinned official runner.

Run from the staged repository root with Python 3.12:
  python -m lab.odin.release.linux_match --candidate candidate.zip --baseline v3.zip \
      --pairs 2 --opening-offset 120 --cpu 0 --log match.jsonl

Each agent is a transient user systemd service. Both sides share the requested
core, appropriate for alternating, non-pondering agents on a one-core signer;
this is explicitly not proof of the unpublished competition CPU's speed.
No ready-state repair or runner shim is used. ZIP bytes are snapshotted once,
audited, freshly extracted for each side/game, and made read-only before play.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid

import chess

# Resolve the harness before importing any helper that itself imports harness.
# The same flags are declared in the full CLI below; parse_known_args performs
# no mutation and prevents accidental use of the historical root harness.
_bootstrap = argparse.ArgumentParser(add_help=False)
_bootstrap.add_argument('--validation-root', type=Path, default=Path(__file__).resolve().parents[3])
_bootstrap.add_argument('--harness-root', type=Path)
_bootstrap_args, _ = _bootstrap.parse_known_args()
ROOT = _bootstrap_args.validation_root.resolve()
HARNESS_ROOT = (_bootstrap_args.harness_root or ROOT/'lab/odin/official-harness-91f70e54').resolve()
if any(name == 'harness' or name.startswith('harness.') for name in sys.modules):
    raise RuntimeError('Harness was imported before the explicit pinned harness selection')
sys.path.insert(0, str(HARNESS_ROOT))
sys.path.insert(1, str(ROOT))

from harness.referee import play_match
from harness.rules import BASE_MS, INCREMENT_MS, INIT_BUDGET_S, PLY_CAP
from harness.sandbox import Agent, AgentFailure, RUNNER
# These helpers contain portable archive/plan code. No Windows runner or
# Windows API is called; the actual command below uses harness/runner.py.
from lab.laptop_match import (
    build_game_plan, candidate_points, extraction_problems, load_openings,
    role_failed, safe_extract, sha256_path, snapshot_archive, snapshot_json,
    verify_snapshot,
)

assert Path(RUNNER).resolve().is_relative_to(HARNESS_ROOT), 'Wrong official runner import'
assert PLY_CAP == 600 and INIT_BUDGET_S == 90.0, 'Wrong referee/rules revision'
MEMORY_LIMIT_BYTES = 2 * 1024**3
THREAD_ENV = (
    'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
    'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS',
    'BLIS_NUM_THREADS',
)
PROPERTIES = (
    'LoadState', 'ActiveState', 'SubState', 'MainPID', 'ControlGroup', 'MemoryCurrent',
    'MemoryPeak', 'MemoryMax', 'MemorySwapMax', 'CPUQuotaPerSecUSec',
    'CPUAffinity', 'RestrictAddressFamilies', 'RuntimeMaxUSec', 'Result',
    'TasksMax', 'NoNewPrivileges', 'LimitFSIZE',
)
TELEMETRY = re.compile(r'^(?:S4|O5) p(?P<game_ply>\d+) d(?P<depth>\d+) n(?P<nodes>\d+) '
                       r's(?P<score>-?\d+) t(?P<elapsed_ms>\d+) b(?P<target_ms>\d+)$')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(payload, sort_keys=True, allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def runner_command(directory, home, cpu, unit, python=None):
    """Argument vectors only: paths never pass through shell interpolation."""
    if cpu < 0 or not re.fullmatch(r'chesstk-[a-zA-Z0-9-]+\.service', unit):
        raise ValueError('Invalid CPU or transient unit name')
    environment = {name: '1' for name in THREAD_ENV}
    environment.update(HOME=str(home), TMPDIR=str(home), TMP=str(home), TEMP=str(home),
                       XDG_CACHE_HOME=str(home/'cache'), PYTHONDONTWRITEBYTECODE='1',
                       PYTHONHASHSEED='0')
    command = [
        'systemd-run', '--user', '--quiet', '--wait', '--pipe', '--collect',
        '--service-type=exec', '--unit='+unit,
        '--property=CPUAffinity='+str(cpu), '--property=CPUQuota=100%',
        '--property=MemoryMax='+str(MEMORY_LIMIT_BYTES),
        '--property=MemorySwapMax=0', '--property=RestrictAddressFamilies=AF_UNIX',
        '--property=RuntimeMaxSec=900', '--property=MemoryAccounting=yes',
        '--property=TasksMax=128', '--property=NoNewPrivileges=yes',
        '--property=LimitFSIZE=268435456',
        '--property=KillMode=control-group', '--property=TimeoutStopSec=5',
        '--property=WorkingDirectory='+str(directory),
    ]
    command += ['--setenv='+key+'='+value for key, value in environment.items()]
    command += ['--', shutil.which('taskset') or 'taskset', '-c', str(cpu),
                str(python or sys.executable), '-B', '-u', str(RUNNER), str(directory)]
    return command


def service_properties(unit):
    command = ['systemctl', '--user', 'show', unit]
    command += ['--property='+name for name in PROPERTIES]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
    result = dict(line.split('=', 1) for line in completed.stdout.splitlines() if '=' in line)
    result['query_returncode'] = completed.returncode
    # Unit errors never contain agent output; retain a small diagnostic.
    if completed.returncode:
        result['query_error'] = completed.stderr[-1000:]
    return result


def envelope_problems(properties, cpu, affinity=None):
    problems = []
    for name, expected in [('MemoryMax', str(MEMORY_LIMIT_BYTES)), ('MemorySwapMax', '0'),
                           ('TasksMax', '128'), ('NoNewPrivileges', 'yes'), ('LimitFSIZE', '268435456')]:
        if properties.get(name) != expected:
            problems.append(f'{name}={properties.get(name)!r}, expected {expected}')
    if properties.get('RestrictAddressFamilies', '').strip() != 'AF_UNIX':
        problems.append('AF_UNIX-only socket creation restriction was not verified')
    # systemctl formats one CPU of quota as one second per second.
    if properties.get('CPUQuotaPerSecUSec') not in ('1s', '1000000us', '1000000'):
        problems.append('100% CPU quota was not verified')
    if affinity is not None and set(affinity) != {cpu}:
        problems.append(f'Actual CPU affinity {affinity!r}, expected [{cpu}]')
    if affinity is None:
        problems.append('Could not inspect service MainPID CPU affinity')
    if properties.get('RuntimeMaxUSec') not in ('15min', '15min 0s', '900s', '900000000us'):
        problems.append('900-second service lifetime ceiling was not verified')
    return problems


def stop_service(unit):
    """Stop the workload cgroup before terminating its systemd-run relay."""
    try:
        stopped = subprocess.run(['systemctl', '--user', 'stop', unit],
                                 capture_output=True, text=True, timeout=12)
        if stopped.returncode == 0:
            return None
    except subprocess.TimeoutExpired:
        stopped = None
    # An exited --collect unit is normally already absent. Inspect before
    # escalating; if it is still active, kill all its service processes.
    props = service_properties(unit)
    if props.get('LoadState') == 'not-found' or props.get('ActiveState') in ('inactive', 'failed'):
        return None
    if props.get('ActiveState') not in ('active', 'activating', 'deactivating', 'reloading'):
        return 'Could not verify service state after a failed stop'
    subprocess.run(['systemctl', '--user', 'kill', '--kill-whom=all', '--signal=KILL', unit],
                   capture_output=True, text=True, timeout=10)
    subprocess.run(['systemctl', '--user', 'stop', unit],
                   capture_output=True, text=True, timeout=12)
    props = service_properties(unit)
    if props.get('LoadState') == 'not-found' or props.get('ActiveState') in ('inactive', 'failed'):
        return None
    return 'Transient service stop was not verified after stop and kill'


def parse_telemetry(stderr):
    return [{key: int(value) for key, value in match.groupdict().items()}
            for line in stderr.splitlines() if (match := TELEMETRY.fullmatch(line))]


class TimedAgent(Agent):
    def __init__(self, directory, home, cpu, unit, role):
        super().__init__(runner_command(directory, home, cpu, unit))
        self.cpu, self.unit, self.role = cpu, unit, role
        self.init_s = None
        self.moves = []
        self.memory_samples = []
        self.envelope_errors = []
        self.cleanup_error = None
        self._stopped = False

    def _sample(self, phase):
        try:
            properties = service_properties(self.unit)
        except (OSError, subprocess.SubprocessError) as exc:
            properties = {'query_error': str(exc)}
        self.memory_samples.append(dict(properties, phase=phase))
        return properties

    def start(self, init_budget_s):
        started = time.monotonic()
        try:
            super().start(init_budget_s)
        finally:
            self.init_s = time.monotonic() - started
        properties = self._sample('after_init')
        affinity = None
        try:
            affinity = sorted(os.sched_getaffinity(int(properties.get('MainPID', 0))))
        except (ValueError, ProcessLookupError, PermissionError, AttributeError):
            pass
        self.envelope_errors = envelope_problems(properties, self.cpu, affinity)
        if self.envelope_errors:
            raise AgentFailure('init')

    def move(self, fen, time_left_ms):
        started = time.monotonic()
        row = {'request': len(self.moves)+1, 'fen': fen, 'time_left_ms': time_left_ms}
        try:
            move = super().move(fen, time_left_ms)
            row.update(ok=True, move=move)
            return move
        except BaseException as exc:
            row.update(ok=False, failure=getattr(exc, 'reason', type(exc).__name__))
            raise
        finally:
            row['elapsed_ms'] = round((time.monotonic()-started)*1000, 3)
            self.moves.append(row)

    def stop(self):
        if self._stopped:
            return
        self._sample('before_stop')
        try:
            self.cleanup_error = stop_service(self.unit)
        except (OSError, subprocess.SubprocessError) as exc:
            self.cleanup_error = str(exc)
        finally:
            # Killing only this relay does not kill the service. Keep this
            # ordering even after a timeout, init failure or KeyboardInterrupt.
            super().stop()
            self._stopped = True

    def report(self):
        durations = [r['elapsed_ms'] for r in self.moves]
        peaks = [int(s['MemoryPeak']) for s in self.memory_samples
                 if str(s.get('MemoryPeak', '')).isdigit()]
        return {'role': self.role, 'cpu': self.cpu, 'unit': self.unit,
                'init_s': None if self.init_s is None else round(self.init_s, 3),
                'move_count': len(self.moves), 'move_total_ms': round(sum(durations), 3),
                'move_max_ms': max(durations, default=0),
                'move_median_ms': statistics.median(durations) if durations else 0,
                'moves': self.moves, 'memory_peak_bytes': max(peaks) if peaks else None,
                'memory_samples': self.memory_samples, 'envelope_errors': self.envelope_errors,
                'cleanup_error': self.cleanup_error,
                'search_telemetry': parse_telemetry(self.stderr_tail),
                'stderr_tail': self.stderr_tail[-12000:]}


def make_readonly(directory):
    paths = sorted(directory.rglob('*'), key=lambda p: len(p.parts), reverse=True)
    for path in paths:
        if path.is_symlink():
            raise ValueError('Symlink in extraction')
        path.chmod(0o555 if path.is_dir() else 0o444)
    directory.chmod(0o555)


def cleanup_owned_tree(directory, owner):
    """Restore modes then remove only this run's explicitly owned temp tree."""
    directory, owner = directory.resolve(), owner.resolve()
    if directory == owner or not directory.is_relative_to(owner):
        raise ValueError('Refusing cleanup outside the exact owned temporary parent')
    if not directory.exists():
        return
    directory.chmod(0o700)
    for path in directory.rglob('*'):
        if not path.is_symlink():
            path.chmod(0o700 if path.is_dir() else 0o600)
    shutil.rmtree(directory)


def runtime_identity():
    cpu_models = []
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.is_file():
        cpu_models = sorted({line.split(':', 1)[1].strip()
                             for line in cpuinfo.read_text(encoding='utf-8').splitlines()
                             if line.startswith('model name')})
    return {'python': platform.python_version(), 'executable': sys.executable,
            'platform': platform.platform(), 'machine': platform.machine(),
            'cpu_models': cpu_models, 'controller_affinity': sorted(os.sched_getaffinity(0)),
            'packages': {name: importlib.metadata.version(name)
                         for name in ('chess', 'numpy', 'numba', 'llvmlite')}}


def run(args):
    if sys.platform != 'linux' or sys.version_info[:2] != (3, 12):
        raise SystemExit('Native runs require Linux and Python 3.12')
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        raise SystemExit('This native signer runner requires Linux x86_64')
    for program in ('systemd-run', 'systemctl', 'taskset'):
        if shutil.which(program) is None:
            raise SystemExit(f'Required program is unavailable: {program}')
    if args.cpu not in os.sched_getaffinity(0):
        raise SystemExit('Requested CPU is outside the controller available CPU affinity')
    if args.log.exists():
        raise SystemExit('Refusing to append to an existing match log')
    fens = load_openings(args.openings)
    release_plan = None
    if args.plan:
        release_plan = json.loads(args.plan.read_text(encoding='utf-8-sig'))
        from lab.odin.release.plan import bind_lane
        plans = bind_lane(release_plan, args.suite, args.lane, args.cpu, fens,
                          sha256_path(args.openings), sha256_path(args.candidate),
                          sha256_path(args.baseline), args.base_ms, args.increment_ms)
        args.pairs = len(plans)//2
    else:
        if args.suite or args.lane:
            raise SystemExit('--suite/--lane require --plan')
        plans = build_game_plan(fens, args.pairs, args.opening_offset, (args.cpu, args.cpu))
    for plan in plans:
        board = chess.Board(plan.fen)
        if not board.is_valid() or board.outcome(claim_draw=True) is not None or board.ply() >= PLY_CAP:
            raise SystemExit(f'Invalid/terminal opening index {plan.opening_index}')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    temporary = Path(tempfile.mkdtemp(prefix='chesstk-linux-'+run_id+'-')).resolve()
    owned_parent = temporary.parent
    agents = []
    preserve = False
    completed = failures = 0
    try:
        snapshots = {role: snapshot_archive(path, role, temporary/'snapshots')
                     for role, path in [('candidate', args.candidate), ('baseline', args.baseline)]}
        for snapshot in snapshots.values():
            snapshot.snapshot_path.chmod(0o444)
        from lab.odin.release.plan import source_provenance
        provenance = source_provenance(ROOT, HARNESS_ROOT)
        if release_plan:
            if release_plan['source_provenance'] != provenance:
                raise SystemExit('Frozen plan source provenance differs from execution files')
            if release_plan['packages'] != runtime_identity()['packages']:
                raise SystemExit('Frozen plan runtime packages differ from installed packages')
        append_jsonl(args.log, {
            'type': 'run_start', 'ts': utc_now(), 'run_id': run_id,
            'runtime': runtime_identity(), 'cpu': args.cpu,
            'fidelity': 'native Linux one-core alternating-agent match; not platform CPU proof',
            'limitations': ['Both non-pondering agents share one logical CPU.',
                           'CPU model/load differs from unpublished tournament host.',
                           'Read-only extraction uses file permissions; no container filesystem namespace.',
                           'AF_UNIX-only socket creation permits local Unix-domain sockets.',
                           'Per-game private temp has no 256 MiB filesystem quota.',
                           'MemoryPeak may be unavailable if a failed service was already collected.'],
            'official_referee_unchanged': True, 'official_runner_unchanged': True,
            'runner_shim': None, 'ready_override': False,
            'base_ms': args.base_ms, 'increment_ms': args.increment_ms,
            'service_runtime_limit_s': 900,
            'init_budget_s': INIT_BUDGET_S, 'ply_cap': PLY_CAP, 'pairs_planned': args.pairs,
            'thread_env': {name: '1' for name in THREAD_ENV},
            'source_provenance': provenance,
            'plan_sha256': sha256_path(args.plan) if args.plan else None,
            'suite': args.suite, 'lane': args.lane, 'harness_root': str(HARNESS_ROOT),
            'openings_sha256': sha256_path(args.openings),
            'candidate': dict(snapshot_json(snapshots['candidate']), entries=snapshots['candidate'].entries),
            'baseline': dict(snapshot_json(snapshots['baseline']), entries=snapshots['baseline'].entries),
            'plans': [asdict(plan) for plan in plans],
        })
        for plan in plans:
            game_dir = temporary/f'game-{plan.game:03d}'
            game_dir.mkdir()
            current = {}
            for colour, role in [('white', plan.white_role), ('black', plan.black_role)]:
                directory, home = game_dir/colour, game_dir/(colour+'-home')
                safe_extract(snapshots[role], directory)
                make_readonly(directory)
                home.mkdir(mode=0o700)
                unit = f'chesstk-{run_id}-{plan.game}-{colour}.service'
                agent = TimedAgent(directory, home, args.cpu, unit, role)
                current[colour] = agent
                agents.append(agent)
            game_start = time.monotonic()
            outcome = play_match(current['white'], current['black'], args.base_ms,
                                 args.increment_ms, PLY_CAP, plan.fen)
            candidate_failure = role_failed('candidate', plan, outcome.result, outcome.termination)
            baseline_failure = role_failed('baseline', plan, outcome.result, outcome.termination)
            extraction_errors = {}
            for colour, role in [('white', plan.white_role), ('black', plan.black_role)]:
                extraction_errors[colour] = extraction_problems(snapshots[role], game_dir/colour)
                verify_snapshot(snapshots[role])
            row = {'type': 'game', 'ts': utc_now(), 'run_id': run_id, **asdict(plan),
                   'result': outcome.result, 'termination': outcome.termination,
                   'candidate_colour': 'white' if plan.white_role == 'candidate' else 'black',
                   'candidate_points': candidate_points(plan, outcome.result),
                   'candidate_failure': candidate_failure, 'baseline_failure': baseline_failure,
                   'candidate_sha256': snapshots['candidate'].sha256,
                   'baseline_sha256': snapshots['baseline'].sha256,
                   'white_sha256': snapshots[plan.white_role].sha256,
                   'black_sha256': snapshots[plan.black_role].sha256,
                   'pgn': outcome.pgn, 'wall_s': round(time.monotonic()-game_start, 3),
                   'extraction_errors': extraction_errors,
                   'white_timing': current['white'].report(), 'black_timing': current['black'].report()}
            append_jsonl(args.log, row)
            completed += 1
            failures += int(candidate_failure)+int(baseline_failure)
            print(f'game {plan.game}/{len(plans)} pair {plan.pair}: candidate '
                  f'{row["candidate_colour"]} {row["candidate_points"]} '
                  f'{outcome.termination}; init '
                  f'{current["white"].init_s:.2f}/{current["black"].init_s:.2f}s', flush=True)
            cleanup_errors = [agent.cleanup_error for agent in current.values() if agent.cleanup_error]
            if cleanup_errors or any(extraction_errors.values()):
                preserve = bool(cleanup_errors)
                raise RuntimeError(f'Cleanup/extraction integrity failed: {cleanup_errors}, {extraction_errors}')
            cleanup_owned_tree(game_dir, temporary)
            if candidate_failure or baseline_failure:
                # Finish this colour pair for comparable failure evidence, but
                # do not spend the signer on more pairs after a protocol issue.
                if plan.game % 2 == 0:
                    break
            if plan.game % 2 == 0 and failures:
                break
        append_jsonl(args.log, {'type': 'run_summary', 'ts': utc_now(), 'run_id': run_id,
                               'games_completed': completed, 'pairs_completed': completed//2,
                               'protocol_failures': failures, 'planned_games': len(plans)})
        return 1 if failures else 0
    except BaseException as exc:
        append_jsonl(args.log, {'type': 'run_error', 'ts': utc_now(), 'run_id': run_id,
                               'error': type(exc).__name__+': '+str(exc), 'games_completed': completed})
        raise
    finally:
        for agent in agents:
            try:
                agent.stop()
            except BaseException as exc:
                preserve = True
                print('Service cleanup error: '+str(exc), file=sys.stderr, flush=True)
            preserve = preserve or bool(agent.cleanup_error)
        if preserve:
            print('Preserved exact temporary tree because service cleanup was not verified: '
                  +str(temporary), file=sys.stderr, flush=True)
        else:
            cleanup_owned_tree(temporary, owned_parent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation-root', type=Path, default=ROOT)
    parser.add_argument('--harness-root', type=Path, default=HARNESS_ROOT)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--suite')
    parser.add_argument('--lane')
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--pairs', type=int, default=2)
    parser.add_argument('--opening-offset', type=int, default=0)
    parser.add_argument('--openings', type=Path, default=ROOT/'lab/openings.fen')
    parser.add_argument('--base-ms', type=int, default=BASE_MS)
    parser.add_argument('--increment-ms', type=int, default=INCREMENT_MS)
    parser.add_argument('--cpu', type=int, required=True)
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    if args.pairs <= 0 or args.opening_offset < 0 or args.cpu < 0 or args.base_ms <= 0 or args.increment_ms < 0:
        parser.error('Invalid pair count, opening offset, CPU or clock')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
