"""Aggregate completed screens without pooling incompatible comparisons."""
import collections,hashlib,io,json
from pathlib import Path
import chess,chess.pgn
HERE=Path(__file__).resolve().parent
results={};total=0;plies=0
for name in ('queen','graded','capture','bucket','bundle','tables'):
    h=HERE/f'match-{name}';summary=json.loads((h/'summary.json').read_text());assert summary['audit']=='PASS'
    plan=json.loads((h/'plan.json').read_text());assert hashlib.sha256((h/'plan.json').read_bytes()).hexdigest()==summary['plan_sha256']
    rows=[json.loads(s) for s in (h/'lane.jsonl').read_text().splitlines()]
    routes=collections.Counter();coverage=[]
    for r in rows:
        if r['type']!='game':continue
        g=chess.pgn.read_game(io.StringIO(r['pgn']));b=g.board();new_calls=0
        for m,t in zip(g.mainline_moves(),r['telemetry']):
            if t['role']=='candidate':
                routes[t['route']]+=1
                if t['route']=='exact' and b.occupied.bit_count()==4:new_calls+=1
            b.push(m)
        if new_calls:coverage.append(dict(opening=r['opening_index'],colour=r['candidate_colour'],points=r['candidate_points'],four_piece_calls=new_calls))
    results[name]=dict(**summary,candidate=plan['candidate'],baseline=plan['baseline'],candidate_routes=dict(routes),four_piece_coverage_games=coverage)
    total+=summary['games'];plies+=summary['legal_plies']
bundle=json.loads((HERE/'bundle-manifest.json').read_text())
for name,files in bundle['files'].items():
    source=HERE/'prototypes'/name
    assert {p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}==files
result=dict(audit='PASS',total_screen_games=total,total_legal_plies=plies,screens=results,
    independent_strength_confirmation_nominated=False,desktop_promoted=False,
    scope='Six complete exploratory 16-game/500ms screens. Controls/platforms differ; do not pool wins or report a combined Elo. No candidate reached the predeclared 60% nomination threshold. Fresh confirmation families remain unused.')
(HERE/'results.json').write_text(json.dumps(result,indent=2))
print(json.dumps(dict(games=total,plies=plies,scores={k:v['score'] for k,v in results.items()},new_table_coverage={k:v['four_piece_coverage_games'] for k,v in results.items() if k in ('bundle','tables')}),indent=2))
