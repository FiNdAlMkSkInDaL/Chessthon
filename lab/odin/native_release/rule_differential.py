"""Independent python-chess oracle over complete legal history traces."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import random
import sys
import time


def build_traces(diagnostics):
    """Prepare and legally replay oracle cases without importing an engine."""
    import chess
    rows = [json.loads(line) for line in diagnostics.read_text(encoding='utf-8-sig').splitlines()
            if line.strip()]
    assert rows and rows[0].get('type')=='metadata', 'Missing diagnostic metadata'
    assert rows[0]['cases']==len(rows)-1, 'Incomplete diagnostic file'
    cases = [c for c in rows if c.get('kind')=='game_diagnostic']
    assert len(cases)==37, ('Expected 37 retained game-history diagnostics',len(cases))
    traces = []
    for case in cases:
        board = chess.Board(case['start_fen'])
        assert board.is_valid(),case['id']
        for uci in case['history_uci']:
            board.push_uci(uci)
            assert board.is_valid(),(case['id'],uci)
        assert board.fen()==case['fen'],('Diagnostic endpoint mismatch',case['id'])
        traces.append((case['start_fen'],case['history_uci']))
    traces += [('6nk/7p/8/8/8/8/P7/KN5R w - - 0 1',
                'b1c3 g8f6 c3b1 f6g8 a2a3 g8f6 b1c3 f6g8 c3b1 h8g7'.split()),
               (chess.STARTING_FEN, 'g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8'.split())]
    for clock in (0,5,98,99,100):
        for fen in ('8/8/8/8/8/k7/2q5/K7 b - - {clock} 300',
                    '7k/7p/8/8/8/8/P7/K7 w - - {clock} 150',
                    '6k1/6p1/8/8/8/8/P4R2/6K1 w - - {clock} 150'):
            traces.append((fen.format(clock=clock),[]))
    rng = random.Random(20260905)
    for _ in range(12):
        board = chess.Board()
        moves = []
        for __ in range(100):
            legal = list(board.legal_moves)
            if not legal:
                break
            move = rng.choice(legal)
            moves.append(move.uci())
            board.push(move)
        traces.append((chess.STARTING_FEN,moves))
    positions = claimable = 0
    for fen,moves in traces:
        board = chess.Board(fen)
        for uci in [None,*moves]:
            if uci is not None:
                board.push_uci(uci)
            assert board.is_valid(),board.fen()
            positions += 1
            claimable += int(board.can_claim_threefold_repetition() or board.can_claim_fifty_moves())
    return traces,{'traces':len(traces),'positions':positions,'claimable_positions':claimable,
                   'diagnostic_endpoints_verified':len(cases),
                   'note':'Some traces deliberately continue past an auto-claim to test predicate boundaries; they are legal-position histories, not complete competition games.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--diagnostics', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--oracle-only',action='store_true',help='Verify all trace legality/endpoints; import no candidate or Numba')
    parser.add_argument('--cycle-heuristic',action='store_true',help='Storm lineage: test state and fifty-move rules, without asserting exact threefold search')
    parser.add_argument('--total-fifty',action='store_true',help='Require the repaired helper to handle every halfmove value')
    parser.add_argument('--cpu',type=int)
    args = parser.parse_args()
    if args.cpu is not None:
        import os
        if os.name=='nt':
            import ctypes
            k=ctypes.windll.kernel32
            k.GetCurrentProcess.restype=ctypes.c_void_p
            k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
            assert k.SetProcessAffinityMask(k.GetCurrentProcess(),1<<args.cpu)
        else:
            os.sched_setaffinity(0,{args.cpu})
    traces,oracle_summary = build_traces(args.diagnostics)
    if args.oracle_only:
        report = dict(oracle_summary,status='PASS',mode='oracle-only; no engine imported')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report),flush=True)
        return
    sys.path.insert(0, str(args.source.resolve()))
    import chess
    import numpy as np
    import core_nb as core
    from board_nb import from_fen, move_uci
    assert Path(core.__file__).resolve().is_relative_to(args.source.resolve()), 'Wrong candidate core import'
    began = time.perf_counter()
    assert core.warmup() and core.NUMBA_READY
    checked = edges = claims = 0
    def inspect(board, keys):
        nonlocal checked, edges, claims
        assert board.is_valid()
        bb, mb, st = core.pack_pos(from_fen(board.fen(en_passant='fen')))
        before = tuple(x.copy() for x in (bb, mb, st))
        moves = np.zeros(core.MAX_MOVES, dtype=np.int32)
        scratch = np.zeros(core.MAX_MOVES, dtype=np.int32)
        undo = np.zeros(7, dtype=np.uint64)
        n = core.gen_legal(bb, mb, st, moves, scratch)
        legal = list(board.legal_moves)
        assert {move_uci(int(m)) for m in moves[:n]} == {m.uci() for m in legal}
        hist = np.array(keys[:-1], dtype=np.uint64)
        repeated = intended = False
        if not args.cycle_heuristic:
            repeated = core.count_key(st[core.KEY], hist, len(hist)) >= 2
            intended = core.intended_threefold_claim_nb(bb, mb, st, moves, n, hist, len(hist), undo)
            assert bool(repeated or intended) == board.can_claim_threefold_repetition(), board.fen()
        if legal:
            # Storm's narrow helper is reached only at halfmove >=99: both
            # callers return first on a cycle. The exact-history foundation
            # calls its total predicate in more contexts. Test each contract.
            fifty = (False if args.cycle_heuristic and not args.total_fifty and board.halfmove_clock < 99
                     else core.fifty_claim_nb(bb, mb, st, moves, n, scratch, undo))
            assert bool(fifty) == board.can_claim_fifty_moves(), (board.fen(), fifty)
            claims += bool(fifty or repeated or intended)
        assert all(np.array_equal(a, b) for a, b in zip(before, (bb, mb, st)))
        # Independent FEN parsing verifies native make/hash/EP and evaluator accumulators.
        if checked % 13 == 0:
            for packed in moves[:n]:
                m = int(packed)
                core.make_nb(bb, mb, st, m, undo)
                board.push_uci(move_uci(m))
                reference = core.pack_pos(from_fen(board.fen(en_passant='fen')))
                assert all(np.array_equal(a, b) for a, b in zip(reference, (bb, mb, st))), board.fen()
                board.pop()
                core.unmake_nb(bb, mb, st, m, undo)
                assert all(np.array_equal(a, b) for a, b in zip(before, (bb, mb, st)))
                edges += 1
        checked += 1
    for fen, moves in traces:
        board = chess.Board(fen)
        keys = [from_fen(board.fen()).key]
        inspect(board, keys)
        for uci in moves:
            board.push_uci(uci)
            keys.append(from_fen(board.fen()).key)
            inspect(board, keys)
    report = {'status': 'PASS', 'positions': checked, 'native_make_undo_edges': edges,
              'oracle_preflight':oracle_summary,
              'claimable_positions': claims, 'traces': len(traces),
              'seconds': time.perf_counter() - began,
              'oracle': 'python-chess 1.11.2 legal moves, can_claim_fifty_moves, independent FEN pack'
                        + (', can_claim_threefold_repetition' if not args.cycle_heuristic else ''),
              'scope': 'Development correctness; no playing-strength inference.',
              'exact_threefold_predicates_tested':not args.cycle_heuristic,
              'total_fifty_helper_tested':args.total_fifty or not args.cycle_heuristic}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n',encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
