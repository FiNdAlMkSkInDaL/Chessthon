"""Fresh-process native operational/development probe; never an Elo gate."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--diagnostics', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--cpu', type=int, default=0)
    ap.add_argument('--hard-ms', type=float, default=1000)
    args = ap.parse_args()
    assert sys.platform == 'linux' and platform.machine() == 'x86_64'
    assert sys.version_info[:2] == (3, 12)
    assert os.sched_getaffinity(0) == {args.cpu}
    sys.path.insert(0, str(args.source.resolve()))
    start = time.perf_counter()
    import agent
    import core_nb as core
    import chess
    from board_nb import from_fen, move_uci
    from movegen_nb import generate_legal
    cold = time.perf_counter() - start
    assert core.NUMBA_READY and core.root_search_nb.nopython_signatures
    assert cold < 90, cold
    print(json.dumps({'event': 'native_ready', 'cold_s': cold,
                      'warmup_s': core.WARMUP_S}), flush=True)
    report = {'source_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(args.source.glob('*.py'))},
              'python': platform.python_version(), 'machine': platform.machine(),
              'packages': {p: importlib.metadata.version(p) for p in
                           ('chess', 'numba', 'numpy', 'llvmlite')},
              'affinity': sorted(os.sched_getaffinity(0)),
              'cold_s': cold, 'warmup_s': core.WARMUP_S, 'positions': [],
              'note': 'Known diagnostic roots, all legal moves, cold TT per root. Development only; no strength inference.'}
    cases = [json.loads(line) for line in args.diagnostics.read_text().splitlines()]
    # Equal clocks on early tactical roots and late repeated-history endings.
    cases = [c for c in cases if c.get('kind') == 'game_diagnostic']
    cases = cases[:5] + sorted(cases[5:], key=lambda c: -len(c['history_uci']))[:7]
    for case in cases:
        board = chess.Board(case['start_fen'])
        keys = [from_fen(board.fen()).key]
        for uci in case['history_uci']:
            board.push_uci(uci)
            keys.append(from_fen(board.fen()).key)
        assert board.fen() == case['fen'] and board.is_valid()
        pos = from_fen(board.fen())
        moves = generate_legal(pos)
        for name in ('TT_KEY', 'TT_MOVE', 'TT_SCORE', 'TT_DEPTH', 'TT_GEN', 'HISTORY', 'KILLERS'):
            getattr(core, name).fill(0)
        kwargs = {'game_zkeys': keys}
        signature = inspect.signature(core.search_root).parameters
        if 'absolute_ply' in signature:
            kwargs['absolute_ply'] = board.ply()
        if 'adjudicate' in signature:
            kwargs['adjudicate'] = False
        began = time.perf_counter()
        result = core.search_root(pos, moves, args.hard_ms, args.hard_ms, **kwargs)
        elapsed = (time.perf_counter() - began) * 1000
        uci = move_uci(result)
        assert chess.Move.from_uci(uci) in board.legal_moves
        assert elapsed <= args.hard_ms + 250, (case['id'], elapsed)
        row = {'id': case['id'], 'fen': board.fen(), 'history_length': len(keys),
               'history_pair': len(set(keys)) < len(keys), 'halfmove': board.halfmove_clock,
               'move': uci, 'elapsed_ms': elapsed, 'info': core.last_info()}
        report['positions'].append(row)
        print(json.dumps({'event': 'position', **{k: row[k] for k in
                         ('id', 'history_length', 'history_pair', 'halfmove', 'move', 'elapsed_ms')},
                          'depth': row['info'].get('depth'), 'nodes': core.last_nodes()}), flush=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
