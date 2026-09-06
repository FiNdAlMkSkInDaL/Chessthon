"""Replay completed development matches; never infer competition-clock flag rate."""
import hashlib, io, json
from collections import Counter, defaultdict
from pathlib import Path
import chess, chess.pgn
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def terminal(board):
    outcome = board.outcome()
    if outcome is None and board.is_repetition(3):
        outcome = chess.Outcome(chess.Termination.THREEFOLD_REPETITION, None)
    if outcome is None and board.is_fifty_moves():
        outcome = chess.Outcome(chess.Termination.FIFTY_MOVES, None)
    if outcome is not None:
        return outcome.result(), outcome.termination.name
    if board.ply() >= 600:
        return '1/2-1/2', 'PLY_CAP'
    return None

def main():
    results = {}
    for folder in sorted((ROOT/'lab/agamemnon_scale').glob('match-backed-*')):
        plan = json.loads((folder/'plan.json').read_text())
        games = []; cold = []; complete_lanes = 0
        for path in sorted(folder.glob('lane*.jsonl')):
            lines = path.read_text().splitlines()
            # A live file may end in a partial JSON record; audit complete records only.
            rows = []
            for i, line in enumerate(lines):
                try: rows.append(json.loads(line))
                except json.JSONDecodeError:
                    assert i == len(lines)-1
            if rows and rows[-1]['type'] == 'summary':
                assert rows[-1]['games'] == 8
                complete_lanes += 1
            for row in rows:
                if row['type'] == 'plan':
                    assert row['think_ms'] == plan['think_ms']
                    assert row['openings_sha256'] == plan['opening_sha256']
                if row['type'] == 'worker':
                    source = plan[row['role']]
                    assert row['metadata']['source_hashes'] == plan['sources'][source]
                    assert row['isolation']['pass']
                    cold.append(row['metadata']['cold_seconds'])
                if row['type'] != 'game': continue
                game = chess.pgn.read_game(io.StringIO(row['pgn']))
                assert game and not game.errors
                board = game.board(); moves = list(game.mainline_moves())
                assert len(moves) == row['plies'] == len(row['telemetry'])
                color = row['candidate_colour'] == 'white'
                for move, telemetry in zip(moves, row['telemetry']):
                    assert terminal(board) is None
                    assert move in board.legal_moves and move.uci() == telemetry['uci']
                    assert telemetry['role'] == ('candidate' if board.turn == color else 'baseline')
                    assert telemetry['route'] in ('search', 'exact', 'fallback', 'forced', 'panic')
                    board.push(move)
                assert terminal(board) == (row['result'], row['termination'])
                points = .5 if row['result'] == '1/2-1/2' else float((row['result'] == '1-0') == color)
                assert points == row['candidate_points']
                games.append(row)
        if not games: continue
        seen = {(g['opening_index'], g['candidate_colour']) for g in games}
        assert len(seen) == len(games)
        complete = complete_lanes == plan['lanes'] and len(games) == plan['games']
        pairs = defaultdict(list)
        for game in games: pairs[game['opening_index']].append(game['candidate_points'])
        counts = Counter(g['candidate_points'] for g in games)
        item = dict(complete=complete, games=len(games), wins=counts[1], draws=counts[.5], losses=counts[0],
                    score=sum(g['candidate_points'] for g in games)/len(games),
                    plies=sum(g['plies'] for g in games), cold_seconds=cold,
                    terminations=dict(Counter(g['termination'] for g in games)),
                    source_binding=True, legal_replay=True,
                    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('lane*.jsonl')})
        item['timing'] = {}
        for role in ('candidate', 'baseline'):
            t = [v for g in games for v in g['telemetry'] if v['role'] == role]
            seconds = np.array([v['seconds'] for v in t])
            item['timing'][role] = dict(moves=len(t), max_seconds=float(seconds.max()),
                mean_seconds=float(seconds.mean()), p99_seconds=float(np.quantile(seconds,.99)),
                routes=dict(Counter(v['route'] for v in t)))
        if complete:
            assert all(len(v) == 2 for v in pairs.values()) and len(pairs) == 8
            scores = np.array([sum(pairs[i])/2 for i in sorted(pairs)])
            rng = np.random.default_rng(616)
            item['opening_paired_bootstrap95'] = np.quantile(
                rng.choice(scores, (20000, len(scores))).mean(axis=1), [.025, .975]).tolist()
            item['decision'] = 'reject' if item['score'] < .5 else ('inconclusive' if item['score'] < .6 else 'eligible_for_independent_confirmation')
        results[folder.name] = item
    report = dict(matches=results, scope='Exposed development openings, fixed500ms per-move wall allowance; source-bound original clock driver. Legal/result audits and opening-paired unadjusted bootstrap, not competition clock certification or independent Elo evidence. Legacy worker policy string says twelve games; frozen plan and completed lanes specify16.')
    (HERE/'match-results.json').write_text(json.dumps(report, indent=2))
    for name, r in results.items():
        print(name, f"{r['wins']}W/{r['draws']}D/{r['losses']}L", r['score'], 'complete', r['complete'], r.get('decision','running'))

if __name__ == '__main__': main()
