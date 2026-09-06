"""Two exact-archive, sequential native fixed-depth benchmarks.

Plan-only performs archive/data audits without importing either engine. Actual
work requires Linux x86-64 Python 3.12, a single pinned CPU, and two fresh child
processes. No source or ZIP is rebuilt. This measures search work, not Elo.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lab.release_audit import audit

EXPECTED = {
    'r2': '15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c',
    'v3': '3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408',
}
REFERENCES = {'r2': ROOT / 'lab/storm/storm_r2_fixed_depth5.json',
              'v3': ROOT / 'lab/storm/v3_fixed_depth5.json'}
THREAD_ENV = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
              'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS',
              'VECLIB_MAXIMUM_THREADS')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_identity(cpu):
    if sys.platform != 'linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise SystemExit('Actual efficiency work requires native Linux x86-64')
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('Actual efficiency work requires Python 3.12')
    affinity = sorted(os.sched_getaffinity(0))
    if affinity != [cpu]:
        raise SystemExit(f'Pin the entire job to CPU {cpu} first; actual affinity {affinity}')
    packages = {name: importlib.metadata.version(name)
                for name in ('chess', 'numpy', 'numba', 'llvmlite')}
    if packages != {'chess': '1.11.2', 'numpy': '2.5.2', 'numba': '0.67.0', 'llvmlite': '0.49.0'}:
        raise SystemExit(f'Unexpected package versions: {packages}')
    return {'platform': platform.platform(), 'machine': platform.machine(),
            'python': platform.python_version(), 'packages': packages, 'affinity': affinity,
            'cpu_models': sorted({line.split(':', 1)[1].strip()
                                  for line in Path('/proc/cpuinfo').read_text().splitlines()
                                  if line.startswith('model name')})}


def reference_data():
    data = {role: json.loads(path.read_text()) for role, path in REFERENCES.items()}
    fens = [p['fen'] for p in data['r2']['positions']]
    if len(fens) != 32 or fens != [p['fen'] for p in data['v3']['positions']]:
        raise SystemExit('References do not contain the same ordered 32 roots')
    if any(d['depth'] != 5 or d['count'] != 32 for d in data.values()):
        raise SystemExit('Expected both references at depth 5 on 32 roots')
    return data


def worker(args):
    runtime = native_identity(args.cpu)
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    started = time.perf_counter()
    import agent  # Exact submission import includes the actual warmup path.
    import core_nb as core
    import numpy as np
    cold_import_s = time.perf_counter() - started
    if not core.NUMBA_READY:
        raise SystemExit('Original NUMBA_READY is false; no readiness override is permitted')
    if not core.root_search_nb.nopython_signatures:
        raise SystemExit('Live root search did not warm a nopython signature')
    from lab.storm.test_selectivity import run_position
    reference = reference_data()[args.role]
    positions = []
    for index, old in enumerate(reference['positions'], 1):
        result = run_position(core, np, old['fen'], 5)
        if result['aborted']:
            raise SystemExit(f'Unexpected fixed-depth abort at position {index}')
        positions.append(result)
    mismatches = [{'position': i, 'field': field, 'reference': old[field], 'native': new[field]}
                  for i, (old, new) in enumerate(zip(reference['positions'], positions), 1)
                  for field in ('fen', 'move', 'score', 'nodes', 'aborted') if old[field] != new[field]]
    nodes = sum(p['nodes'] for p in positions)
    seconds = sum(p['seconds'] for p in positions)
    result = {'role': args.role, 'archive_sha256': EXPECTED[args.role], 'runtime': runtime,
              'count': len(positions), 'depth': 5, 'cold_agent_import_s': cold_import_s,
              'warmup_s': core.WARMUP_S, 'original_numba_ready': bool(core.NUMBA_READY),
              'root_nopython_signatures': [str(s) for s in core.root_search_nb.nopython_signatures],
              'nodes': nodes, 'seconds': seconds, 'nodes_per_second': nodes / seconds,
              'nanoseconds_per_node': seconds * 1e9 / nodes, 'positions': positions,
              'reference_sha256': sha(REFERENCES[args.role]), 'reference_mismatches': mismatches}
    args.output.write_text(json.dumps(result, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--r2', type=Path)
    parser.add_argument('--v3', type=Path)
    parser.add_argument('--cpu', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--role', choices=('r2', 'v3'), help=argparse.SUPPRESS)
    parser.add_argument('--source', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    if args.r2 is None or args.v3 is None:
        parser.error('--r2 and --v3 exact archive paths are required')
    reference_data()
    inputs = {role: Path(getattr(args, role)).resolve() for role in EXPECTED}
    manifests = {role: audit(path) for role, path in inputs.items()}
    for role, manifest in manifests.items():
        if manifest['archive_sha256'] != EXPECTED[role]:
            raise SystemExit(f'{role}: archive hash is not the frozen signed candidate')
        if any('/' in e['name'] or not e['name'].endswith('.py') for e in manifest['entries']):
            raise SystemExit('Expected source-only flat archives')
    report = {'mode': 'native fixed-depth efficiency', 'cpu': args.cpu,
              'method': 'Two fresh exact-agent imports, sequential processes; identical ordered roots; TT/history/killers cleared per root; depth 1 through 5 with full windows.',
              'limitations': ['Same nominal depth does not mean equal selective search or playing strength.',
                              'Per-node times compare different engine node mixes; they are not a pure evaluation microbenchmark.',
                              'Fixed-depth work uses no live deadline or adaptive time allocation.',
                              'One sequential sample per archive; same signer CPU, not the organiser CPU.',
                              'Historical site roots are diagnostics, not holdout games.'],
              'archives': {r: m['archive_sha256'] for r, m in manifests.items()},
              'provenance': {p.relative_to(ROOT).as_posix(): sha(p) for p in
                             [Path(__file__).resolve(), ROOT / 'lab/storm/test_selectivity.py',
                              ROOT / 'lab/release_audit.py', *REFERENCES.values()]}}
    if args.plan_only:
        report['mode'] = 'plan only; no engine imports'
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return
    report['runtime'] = native_identity(args.cpu)
    results = {}
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='storm-native-efficiency-') as temporary:
        owner = Path(temporary).resolve()
        for role in ('r2', 'v3'):
            source = owner / role
            source.mkdir()
            with zipfile.ZipFile(inputs[role]) as archive:
                for entry in manifests[role]['entries']:
                    data = archive.read(entry['name'])
                    if hashlib.sha256(data).hexdigest() != entry['sha256']:
                        raise SystemExit('Archive member changed after audit')
                    (source / entry['name']).write_bytes(data)
            for path in source.iterdir():
                path.chmod(0o444)
            source.chmod(0o555)
            output = owner / f'{role}.json'
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **{k: '1' for k in THREAD_ENV})
            try:
                subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                                '--role', role, '--source', str(source), '--cpu', str(args.cpu),
                                '--output', str(output)], env=env, cwd=owner, check=True, timeout=100)
                if sha(inputs[role]) != EXPECTED[role]:
                    raise SystemExit('Original archive changed during comparison')
                if any(sha(source / e['name']) != e['sha256'] for e in manifests[role]['entries']):
                    raise SystemExit('Extracted engine source changed during comparison')
                results[role] = json.loads(output.read_text())
                print(f"{role}: {results[role]['nodes']} nodes in {results[role]['seconds']:.6f}s, "
                      f"warmup {results[role]['warmup_s']:.3f}s", flush=True)
            finally:
                # Restore only the exact directory created above for managed cleanup.
                source.chmod(0o700)
                for path in source.iterdir():
                    path.chmod(0o600)
    r2, v3 = results['r2'], results['v3']
    report.update({'engines': results, 'total_job_s': time.perf_counter() - started,
                   'search_time_speedup_v3_over_r2': v3['seconds'] / r2['seconds'],
                   'node_count_ratio_v3_over_r2': v3['nodes'] / r2['nodes'],
                   'node_throughput_ratio_r2_over_v3': r2['nodes_per_second'] / v3['nodes_per_second'],
                   'same_selected_move_count': sum(a['move'] == b['move']
                                                   for a, b in zip(r2['positions'], v3['positions'])),
                   'reference_parity': all(not r['reference_mismatches'] for r in results.values())})
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('engines', 'provenance')}, indent=2))


if __name__ == '__main__':
    main()
