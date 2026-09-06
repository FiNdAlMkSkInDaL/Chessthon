"""Export the separate four-game site-opening stress test, with exact clocks.

Does not pool these selected historical positions with the native holdout.
"""
import io
import json
from pathlib import Path
import re
import statistics

import chess
import chess.pgn


HERE = Path(__file__).resolve().parent
TELEMETRY = re.compile(r"S4 p(\d+) d(\d+) n(\d+) s(-?\d+) t(\d+) b(\d+)")


def main():
    selection = json.loads((HERE / 'site_stress_selection.json').read_text())
    rows = [json.loads(line) for line in (HERE / 'site_stress_r2_vs_v3.jsonl').read_text().splitlines()
            if line.strip()]
    starts = {r['run_id']: r for r in rows if r['type'] == 'run_start'}
    games = [r for r in rows if r['type'] == 'game']
    report = {'purpose': selection['purpose'], 'selection': selection['selection'],
              'candidate': selection['candidate'], 'baseline': selection['baseline'],
              'games_completed': len(games), 'games_planned': 4,
              'complete': len(games) == 4 and any(r['type'] == 'run_summary' for r in rows),
              'limitations': selection['limitations'] + [
                  'The lab runner shim is used; actual readiness states and overrides appear below.',
                  'memory_observed samples the Windows venv launcher, so its RSS is not reported as engine memory.',
                  'S4 telemetry measures native search only; complete move time comes from referee-facing timing.'
              ], 'games': []}
    pgndata = []
    for row in games:
        start = starts[row['run_id']]
        for role in ('candidate', 'baseline'):
            assert row[role + '_sha256'] == selection[role]['sha256']
        chosen = selection['positions'][row['opening_index']]
        assert row['fen'] == chosen['fen']
        parsed = chess.pgn.read_game(io.StringIO(row['pgn']))
        assert parsed is not None and not parsed.errors
        parsed.headers['Event'] = 'Storm r2 supplementary site-opening stress'
        parsed.headers['Site'] = 'Windows local; separate from native holdout'
        parsed.headers['Date'] = row['ts'][:10].replace('-', '.')
        parsed.headers['Round'] = str(row['game'])
        parsed.headers['TimeControl'] = '120+0.5'
        parsed.headers['SourceOpeningIndex'] = str(chosen['site_index'])
        details = {'game': row['game'], 'pair': row['pair'],
                   'source_site_index': chosen['site_index'], 'source_day1_round': chosen['day1_round'],
                   'candidate_colour': row['candidate_colour'], 'result': row['result'],
                   'termination': row['termination'], 'candidate_points': row['candidate_points'],
                   'candidate_failure': row['candidate_failure'], 'baseline_failure': row['baseline_failure'],
                   'post_game_archive_files_unchanged': row['post_game_archive_files_unchanged'],
                   'post_game_extraction_problems': row['post_game_extraction_problems'],
                   'game_wall_s': row['elapsed_s']}
        for colour in ('white', 'black'):
            timing = row[colour + '_timing']
            role = row[colour + '_role']
            parsed.headers[colour.title()] = 'Storm r2' if role == 'candidate' else 'Signed v3'
            moves = timing['moves']
            diag = timing['runner_diagnostics'][-1] if timing['runner_diagnostics'] else {}
            states = diag.get('numba', {})
            telemetry = [dict(zip(('game_ply', 'depth', 'nodes', 'score', 'search_ms', 'soft_ms'),
                                 map(int, match)))
                         for match in TELEMETRY.findall(timing.get('stderr_tail', ''))]
            final_clock = None
            if moves:
                last = moves[-1]
                final_clock = (last['time_left_ms'] - last['elapsed_ms']
                               + (start['increment_ms'] if last['ok'] else 0)) / 1000
            details[role] = {'colour': colour, 'cpu': timing['cpu'], 'moves': len(moves),
                             'init_s': timing['init_s'], 'clock_left_s': final_clock,
                             'thinking_s': sum(m['elapsed_ms'] for m in moves) / 1000,
                             'first20_s': sum(m['elapsed_ms'] for m in moves[:20]) / 1000
                             if len(moves) >= 20 else None,
                             'max_move_s': max((m['elapsed_ms'] for m in moves), default=0) / 1000,
                             'original_ready': states.get('original_ready'),
                             'effective_ready': states.get('effective_ready'),
                             'override_applied': states.get('override_applied'),
                             'compiled': states.get('compiled'), 'envelope': diag.get('envelope'),
                             'telemetry_searches': len(telemetry),
                             'mean_completed_depth': statistics.mean(t['depth'] for t in telemetry)
                             if telemetry else None, 'telemetry': telemetry}
        consumed = {'white': 0, 'black': 0}
        for node in parsed.mainline():
            colour = 'white' if node.parent.board().turn else 'black'
            move = row[colour + '_timing']['moves'][consumed[colour]]
            assert node.move.uci() == move['move'] and move['ok']
            node.set_clock((move['time_left_ms'] - move['elapsed_ms'] + start['increment_ms']) / 1000)
            consumed[colour] += 1
        details['game_plies'] = sum(consumed.values())
        final_board = parsed.end().board()
        details['final_fen'] = final_board.fen()
        details['final_material_white_minus_black'] = sum(
            len(final_board.pieces(piece, chess.WHITE)) * value
            - len(final_board.pieces(piece, chess.BLACK)) * value
            for piece, value in ((1, 1), (2, 3), (3, 3), (4, 5), (5, 9)))
        report['games'].append(details)
        pgndata.append(str(parsed))
    scores = [g['candidate_points'] for g in report['games']]
    report['wins'], report['draws'], report['losses'] = (scores.count(v) for v in (1, 0.5, 0))
    report['candidate_failures'] = sum(g['candidate_failure'] for g in report['games'])
    report['baseline_failures'] = sum(g['baseline_failure'] for g in report['games'])
    report['readiness_overrides'] = sum(bool(g[role]['override_applied'])
                                        for g in report['games'] for role in ('candidate', 'baseline'))
    (HERE / 'site_stress_r2_vs_v3_report.json').write_text(json.dumps(report, indent=2) + '\n')
    (HERE / 'site_stress_r2_vs_v3.pgn').write_text('\n\n'.join(pgndata) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('games', 'limitations')}, indent=2))


if __name__ == '__main__':
    main()
