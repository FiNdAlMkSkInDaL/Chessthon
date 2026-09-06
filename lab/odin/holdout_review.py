"""Read-only legal and descriptive review of Storm's fixed native v3 holdout.

No engine import, search, best-move label, or evaluation oracle is used.
Run: python -m lab.odin.holdout_review
"""
from __future__ import annotations
import hashlib
import ast
import io
import json
import statistics
import time
from collections import Counter
from pathlib import Path
import chess
import chess.pgn

ROOT = Path(__file__).resolve().parents[2]
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}

# Literal-data inspection only: importing the submission would trigger JIT.
_constants = {}
for _node in ast.parse((ROOT / 'storm/eval_nb.py').read_text()).body:
    if isinstance(_node, ast.Assign) and len(_node.targets) == 1 and isinstance(_node.targets[0], ast.Name):
        _name = _node.targets[0].id
        if _name in {'MG_VALUE', 'EG_VALUE', 'PHASE_INC', 'MG_PST', 'EG_PST', 'TEMPO'}:
            _constants[_name] = ast.literal_eval(_node.value)

def static_pesto(board):
    """Exact readable root evaluator arithmetic, without engine imports."""
    mg = eg = phase = 0
    for square, piece in board.piece_map().items():
        pt = piece.piece_type - 1
        sign = 1 if piece.color else -1
        pst_square = square ^ 56 if piece.color else square
        mg += sign * (_constants['MG_VALUE'][pt] + _constants['MG_PST'][pt][pst_square])
        eg += sign * (_constants['EG_VALUE'][pt] + _constants['EG_PST'][pt][pst_square])
        phase += _constants['PHASE_INC'][pt]
    phase = min(phase, 24)
    score = (mg * phase + eg * (24 - phase)) // 24
    return (score if board.turn else -score) + _constants['TEMPO']

def direct_filter_rejections(board, seen, static_score):
    """Source-exact cheap rejection rules, excluding deeper deadline-limited scans.

    If every move is rejected, the real filter restores all legal moves.
    These records alone do not prove a move was absent from the final root.
    """
    if static_score < 80:
        return []
    rejected = []
    for move in board.legal_moves:
        san = board.san(move)
        reasons = []
        zeroing = board.is_zeroing(move)
        fifty = board.halfmove_clock
        board.push(move)
        if not board.is_checkmate():
            if board.is_stalemate() or board.is_insufficient_material():
                reasons.append('immediate_draw')
            if fifty >= 90 and not zeroing:
                reasons.append('quiet_with_halfmove_at_least_90')
            if seen[board._transposition_key()] >= 1:
                reasons.append('second_occurrence')
        board.pop()
        if reasons:
            rejected.append({'uci': move.uci(), 'san': san, 'reasons': reasons})
    return rejected

_filter_functions = {'_deadline_expired', '_auto_claim_now', '_opponent_can_force_auto_claim', 'filter_root_moves'}
_history_tree = ast.parse((ROOT / 'storm/history.py').read_text())
_filter_module = ast.Module(body=[n for n in _history_tree.body if isinstance(n, ast.FunctionDef) and n.name in _filter_functions], type_ignores=[])

def replay_complete_filter(board, seen, static_score):
    """Run only source root-filter functions, without importing agent/JIT code.

    Deadline is disabled to enumerate intended filter behavior. Native recorded
    roots have a 50ms cap; deeper rejected-move sets can therefore differ.
    """
    namespace = {'chess': chess, 'time': time, '_seen': seen.copy(), 'FIFTY_ZERO_FROM': 90}
    exec(compile(_filter_module, 'storm/history.py', 'exec'), namespace)
    legal = list(board.legal_moves)
    kept = namespace['filter_root_moves'](board, legal, static_score >= 80)
    return {'deadline_disabled': True, 'legal': [m.uci() for m in legal],
            'kept': [m.uci() for m in kept],
            'rejected': [{'uci': m.uci(), 'san': board.san(m)} for m in legal if m not in kept]}

def material(board, colour):
    return sum(v * len(board.pieces(p, colour)) for p, v in VALUES.items())

def run():
    games, sources = [], []
    for lane in ('a', 'b'):
        path = ROOT / f'lab/storm/holdout-r2-lane-{lane}.jsonl'
        raw = path.read_bytes()
        sources.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(raw).hexdigest()})
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        start = next(r for r in rows if r.get('type') == 'run_start')
        for row in rows:
            if row.get('type') != 'game':
                continue
            colour = 'white' if row['white_role'] == 'candidate' else 'black'
            own = colour == 'white'
            pg = chess.pgn.read_game(io.StringIO(row['pgn']))
            assert pg is not None and not pg.errors
            board = chess.Board(row['fen'])
            assert pg.board().fen() == board.fen()
            counts = {'white': 0, 'black': 0}
            seen = Counter()
            telemetry = {t['game_ply']: t for t in row[colour + '_timing']['s4_telemetry']}
            trace = []
            for ply, move in enumerate(pg.mainline_moves()):
                side = 'white' if board.turn else 'black'
                req = row[side + '_timing']['moves'][counts[side]]
                assert req['fen'] == board.fen() and req['move'] == move.uci() and move in board.legal_moves
                assert board.outcome(claim_draw=True) is None
                entry = {'ply': ply + 1, 'fullmove': board.fullmove_number, 'side': side,
                         'san': board.san(move), 'uci': move.uci(), 'fen': board.fen(),
                         'in_check': board.is_check(), 'legal_count': board.legal_moves.count(),
                         'material_balance': material(board, own) - material(board, not own),
                         'piece_count': len(board.piece_map()),
                         'request': counts[side] + 1, 'clock_ms': req['time_left_ms'],
                         'elapsed_ms': req['elapsed_ms'],
                         'after_clock_ms': req['time_left_ms'] - req['elapsed_ms'] + start['increment_ms'],
                         'telemetry': telemetry.get(counts[side] * 2) if side == colour else None}
                if side == colour:
                    seen[board._transposition_key()] += 1
                    entry['static_root_score'] = static_pesto(board)
                    entry['direct_filter_rejections'] = direct_filter_rejections(board, seen, entry['static_root_score'])
                    if lane == 'a' and row['game'] == 12 and board.fullmove_number in {60,61,65,70,72,83}:
                        entry['full_root_filter_replay'] = replay_complete_filter(board, seen, entry['static_root_score'])
                board.push(move)
                if side == colour:
                    seen[board._transposition_key()] += 1
                entry['fen_after'] = board.fen()
                trace.append(entry)
                counts[side] += 1
            outcome = board.outcome(claim_draw=True)
            assert outcome is not None
            expected = 'draw' if outcome.winner is None else 'white' if outcome.winner else 'black'
            assert row['result'] == expected and row['termination'] == outcome.termination.name.lower()
            own_trace = [t for t in trace if t['side'] == colour]
            scored = [t for t in own_trace if t['telemetry'] is not None]
            deltas = []
            for previous, current in zip(scored, scored[1:]):
                delta = current['telemetry']['score'] - previous['telemetry']['score']
                if abs(previous['telemetry']['score']) < 31000 and abs(current['telemetry']['score']) < 31000:
                    deltas.append({'previous_ply': previous['ply'], 'ply': current['ply'], 'delta': delta})
            result = 'draw' if row['result'] == 'draw' else 'win' if row['result'] == colour else 'loss'
            games.append({'id': f'{lane}-{row["game"]:02d}', 'opening_index': row['opening_index'],
                          'lane': lane, 'game': row['game'], 'colour': colour, 'result': result,
                          'termination': row['termination'], 'plies': len(trace), 'initial_fen': row['fen'],
                          'final_fen': board.fen(), 'final_material_balance': material(board, own) - material(board, not own),
                          'own_moves': len(own_trace), 'first20_s': sum(t['elapsed_ms'] for t in own_trace[:20]) / 1000,
                          'final_clock_s': own_trace[-1]['after_clock_ms'] / 1000,
                          'min_clock_after_s': min(t['after_clock_ms'] for t in own_trace) / 1000,
                          'peak_score': max((t['telemetry']['score'] for t in scored), default=None),
                          'opening_score': scored[0]['telemetry']['score'] if scored else None,
                          'last_score': scored[-1]['telemetry']['score'] if scored else None,
                          'largest_score_drops': sorted(deltas, key=lambda d:d['delta'])[:5],
                          'moves_above_5s': sum(t['elapsed_ms'] > 5000 for t in own_trace),
                          'moves_over_3x_soft': sum(t['elapsed_ms'] > 3*t['telemetry']['target_ms'] for t in scored),
                          'trace': trace})
    summary = {'sources': sources, 'notes': [
        'All recorded scores are Storm own-perspective estimates, not independent objective labels.',
        'Telemetry p is twice the agent request index, measured from its first served FEN.',
        'Score deterioration includes the opponent reply and search/TT/clock changes; it is not move-loss ground truth.',
        'All game FENs and UCIs legally replayed and automatic-claim terminal results matched.',
        'Direct-filter rejections reproduce cheap source rules, excluding deeper deadline scans and all-rejected fallback; they are not a complete root-filter replay.',
        'Synthetic opening distribution differs from site starts; do not extrapolate matchup Elo to the leaderboard.'
    ], 'games': len(games), 'plies_replayed': sum(g['plies'] for g in games),
        'wdl': dict(Counter(g['result'] for g in games)),
        'by_result': {result: {'games': sum(g['result'] == result for g in games),
           'mean_final_clock_s': statistics.mean(g['final_clock_s'] for g in games if g['result'] == result),
           'mean_first20_s': statistics.mean(g['first20_s'] for g in games if g['result'] == result),
           'mean_plies': statistics.mean(g['plies'] for g in games if g['result'] == result)}
           for result in ('win','draw','loss')},
        'game_reviews': games}
    out = ROOT / 'lab/odin/holdout_review.json'
    out.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k != 'game_reviews'}, indent=2))
    for game in games:
        print(json.dumps({k:v for k,v in game.items() if k != 'trace'}))

if __name__ == '__main__':
    run()
