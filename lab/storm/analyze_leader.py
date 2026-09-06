"""Reproduce SoberJackson clock observations from three saved public game pages.

Only public team links and their visible PGN download data URLs are used.
No engine analysis, hidden endpoints, authentication, or page internals needed.
"""
from collections import Counter
import hashlib
import html
import io
import json
from pathlib import Path
import re
from statistics import mean, pstdev
from urllib.parse import unquote

import chess
import chess.pgn

HERE = Path(__file__).resolve().parent


def clean(value):
    return html.unescape(re.sub(r'<[^>]*>', '', value)).strip()


def main():
    team = (HERE/'soberjackson_team_snapshot.html').read_text(encoding='utf-8')
    games = []
    for row in re.findall(r'<tr[^>]*>.*?</tr>', team):
        match = re.search(r'data-href="(/game/[^?"]+)[^"]*"', row)
        if not match:
            continue
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row)
        games.append({'match_id': match.group(1).split('/')[-1],
                      'round': int(re.search(r'Rated (\d+)', cells[0]).group(1)),
                      'colour': clean(cells[1]).lower(), 'opponent': clean(cells[2]),
                      'outcome': clean(cells[3]).lower(), 'opening': clean(cells[4])})
    assert [g['round'] for g in games[:3]] == [15, 14, 13]
    metadata = json.loads((HERE/'soberjackson_games_metadata.json').read_text(encoding='utf-8'))
    ladder = (HERE/'leaderboard_snapshot.html').read_text(encoding='utf-8')
    teams = []
    for row in re.findall(r'<tr[^>]*>.*?</tr>', ladder):
        rank = re.search(r'class="ladder-rank">(\d+)', row)
        if not rank:
            continue
        name = re.search(r'class="ladder-bot-name">(.*?)</span>', row).group(1)
        small = re.search(r'<small>(.*?)</small>', name)
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row)
        teams.append({'rank': int(rank.group(1)), 'rating': int(clean(cells[3])),
                      'bot': clean(name.split('<small>')[0]),
                      'team': clean(small.group(1)) if small else clean(name)})
    selected = []
    all_moves = []
    for info in games[:3]:
        path = HERE/('soberjackson_game_'+info['match_id']+'.html')
        page = path.read_text(encoding='utf-8')
        matches = re.findall(r'<a[^>]+download="([^"]+\.pgn)"[^>]+href="(data:application/x-chess-pgn;[^"]+)"', page)
        assert len(matches) == 1, (path, len(matches))
        download_name, url = matches[0]
        pgn_text = unquote(html.unescape(url).split(',', 1)[1])
        pgn_path = HERE/('soberjackson_round_'+str(info['round'])+'.pgn')
        pgn_path.write_text(pgn_text+'\n', encoding='utf-8')
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        assert not game.errors
        board = game.board()
        colour = info['colour'] == 'white'
        counts = Counter()
        clocks = {True: 120.0, False: 120.0}
        moves = []
        for node in game.mainline():
            turn = board.turn
            counts[turn] += 1
            assert node.move in board.legal_moves
            clock = node.clock()
            assert clock is not None
            elapsed = clocks[turn]+.5-clock
            assert elapsed >= -.001
            move = {'round': info['round'], 'game_ply': len(moves),
                    'ours': turn == colour, 'side_move_number': counts[turn],
                    'move_uci': node.move.uci(), 'move_san': board.san(node.move),
                    'fen': board.fen(), 'clock_before_s': clocks[turn],
                    'elapsed_s': round(elapsed, 3), 'clock_after_s': clock,
                    'legal_moves': board.legal_moves.count(),
                    'phase': min(24, sum(len(board.pieces(p,c))*w for p,w in ((2,1),(3,1),(4,2),(5,4)) for c in chess.COLORS))}
            moves.append(move)
            clocks[turn] = clock
            board.push(node.move)
        actual = board.outcome(claim_draw=True)
        assert actual and actual.result() == game.headers['Result']
        ours = [r for r in moves if r['ours']]
        theirs = [r for r in moves if not r['ours']]
        bins = [(1,10),(11,20),(21,40),(41,60),(61,150)]
        observed = next(m for m in metadata if info['match_id'] in m['url'])
        assert observed['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
        record = dict(info, source=observed, download_filename=download_name,
                      opponent_ladder=next(t for t in teams if info['opponent'] in (t['team'], t['bot'])),
                      pgn_sha256=hashlib.sha256(pgn_path.read_bytes()).hexdigest(),
                      pgn_headers=dict(game.headers), game_plies=len(moves),
                      own_moves=len(ours), opponent_moves=len(theirs),
                      remaining_s=clocks[colour], opponent_remaining_s=clocks[not colour],
                      total_thinking_s=round(sum(r['elapsed_s'] for r in ours),3),
                      first20_s=round(sum(r['elapsed_s'] for r in ours[:20]),3),
                      opponent_first20_s=round(sum(r['elapsed_s'] for r in theirs[:20]),3),
                      first_move_s=ours[0]['elapsed_s'],
                      mean_move_s=round(mean(r['elapsed_s'] for r in ours),3),
                      elapsed_below100ms=sum(r['elapsed_s'] < .1 for r in ours),
                      elapsed_above5s=sum(r['elapsed_s'] > 5 for r in ours),
                      slowest_move=max(ours,key=lambda r:r['elapsed_s']),
                      own_bins_mean_s={f'{lo}-{hi}': round(mean(rs),3) if (rs:=[r['elapsed_s'] for r in ours if lo<=r['side_move_number']<=hi]) else None for lo,hi in bins},
                      own_phase_mean_s={name: round(mean(rs),3) if (rs:=[r['elapsed_s'] for r in ours if lo<=r['phase']<=hi]) else None for name,lo,hi in [('19-24',19,24),('7-18',7,18),('0-6',0,6)]})
        selected.append(record)
        all_moves.extend(moves)
    report = {'selection': 'Three newest game links on the saved public team page: rated 15,14,13.',
              'team_source': json.loads((HERE/'soberjackson_team_snapshot_metadata.json').read_text(encoding='utf-8')),
              'ladder_source': json.loads((HERE/'leaderboard_snapshot_metadata.json').read_text(encoding='utf-8')),
              'base_s': 120.0, 'increment_s': .5,
              'method': 'Elapsed = previous same-side PGN clock + increment - next same-side PGN clock.',
              'games': selected, 'mean_first20_s': round(mean(g['first20_s'] for g in selected),3),
              'stddev_first20_s': round(pstdev(g['first20_s'] for g in selected),3),
              'mean_remaining_s': round(mean(g['remaining_s'] for g in selected),3),
              'limitations': ['Three different games against different opponents are not a controlled engine comparison.',
                              'No internal search-depth, node-count, evaluation or algorithm information is exposed by these clocks.',
                              'Opening identities and colours are taken from the public team table because PGN White/Black headers are placeholders.']}
    (HERE/'soberjackson_summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (HERE/'soberjackson_moves.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in all_moves),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
