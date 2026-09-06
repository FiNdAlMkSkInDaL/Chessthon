"""Read only the public competition leaderboard; retain timestamped evidence.

Use --offline to parse the saved HTML without fetching a new observation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
URL = 'https://aichessathon.com/leaderboard'


def text(fragment):
    return html.unescape(re.sub(r'<[^>]*>', '', fragment)).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    snapshot = HERE/'leaderboard_snapshot.html'
    metadata_path = HERE/'leaderboard_snapshot_metadata.json'
    if not args.offline:
        with urlopen(Request(URL, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as response:
            raw = response.read()
            metadata = {'url': URL, 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                        'server_date': response.headers.get('date'),
                        'cache_control': response.headers.get('cache-control'),
                        'sha256': hashlib.sha256(raw).hexdigest()}
        snapshot.write_bytes(raw)
        metadata_path.write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    source = snapshot.read_text(encoding='utf-8')
    teams = []
    for row in re.findall(r'<tr[^>]*>.*?</tr>', source):
        rank = re.search(r'class="ladder-rank">(\d+)', row)
        if not rank:
            continue
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row)
        name = re.search(r'class="ladder-bot-name">(.*?)</span>', row).group(1)
        small = re.search(r'<small>(.*?)</small>', name)
        teams.append({'rank': int(rank.group(1)),
                      'bot': text(name.split('<small>')[0]),
                      'team': text(small.group(1)) if small else text(name),
                      'university': text(cells[2]), 'rating': int(text(cells[3])),
                      'games': int(text(cells[4])), 'record_wdl': text(cells[5]),
                      'url': 'https://aichessathon.com'+html.unescape(re.search(r'data-href="([^"]+)"', row).group(1))})
    assert teams and [t['rank'] for t in teams[:5]] == [1,2,3,4,5]
    day1 = json.loads((HERE/'day1_summary.json').read_text(encoding='utf-8'))
    opponents = []
    for game in day1['games']:
        matches = [t for t in teams if game['opponent'].casefold() in (t['bot'].casefold(), t['team'].casefold())]
        assert len(matches) == 1, (game['opponent'], matches)
        opponents.append(dict(matches[0], round=game['round'], our_result=game['outcome']))
    result = {'metadata': metadata, 'teams_in_snapshot': len(teams), 'top5': teams[:5],
              'samson': next(t for t in teams if t['bot']=='Samson'), 'day1_opponents': opponents,
              'limitations': ['Ratings are at snapshot time, not pre-game ratings.',
                              'Leaderboard outcomes do not identify opponents\' algorithms or prove opponent schedules.']}
    (HERE/'leaderboard_comparison.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
