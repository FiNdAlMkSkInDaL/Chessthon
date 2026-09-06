"""Replay every declared pair and bind it to frozen sources and helpers."""
import argparse,collections,hashlib,io,json,sys
from pathlib import Path
import chess,chess.pgn
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'lab/tempest_build'))
from review_v6_games import terminal
ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);a=ap.parse_args();h=HERE/a.name
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((h/'plan.json').read_text());rows=[json.loads(s) for s in (h/'lane.jsonl').read_text().splitlines()]
assert rows[-1]['type']=='summary' and rows[-1]['games']==plan['games']
assert rows[0]['indices']==plan['indices'] and rows[0]['think_ms']==plan['think_ms'] and rows[0]['cpu']==plan['cpu']
opening=ROOT/'lab/odin/fast/generation-openings/screen.fen';assert sha(opening)==plan['opening_sha256']==rows[0]['openings_sha256']
fens=[s for s in opening.read_text().splitlines() if s.strip() and not s.startswith('#')]
for name,digest in plan['helpers_sha256'].items():assert sha(h/name)==digest
for source,expected in plan['sources'].items():assert {p.name:sha(p) for p in (ROOT/source).iterdir() if p.is_file() and p.suffix in ('.py','.npz')}==expected
games=[];workers=[];pairs=collections.defaultdict(list);plies=0
for r in rows:
    if r['type']=='worker':
        assert r['metadata']['source_hashes']==plan['sources'][plan[r['role']]]
        assert r['metadata']['worker_sha256']==plan['helpers_sha256']['clock_worker.py'] and r['isolation']['pass'];workers.append(r)
    if r['type']=='game':
        assert r['opening_index'] in plan['indices'];g=chess.pgn.read_game(io.StringIO(r['pgn']));assert not g.errors
        b=g.board();assert b.fen()==chess.Board(fens[r['opening_index']]).fen();own=r['candidate_colour']=='white'
        moves=list(g.mainline_moves());assert len(moves)==r['plies']==len(r['telemetry'])
        for m,t in zip(moves,r['telemetry']):
            assert terminal(b) is None and m in b.legal_moves and m.uci()==t['uci']
            assert t['role']==('candidate' if b.turn==own else 'baseline') and t['seconds']>=0
            b.push(m);plies+=1
        result=terminal(b);assert result is not None and result.result()==r['result']==g.headers['Result']
        assert result.termination.name==r['termination'] or (r['termination']=='PLY_CAP' and b.ply()>=600)
        points=.5 if result.winner is None else float(result.winner==own);assert points==r['candidate_points']
        pairs[r['opening_index']].append(own);games.append(r)
assert len(games)==16 and len(workers)==2 and set(pairs)==set(plan['indices'])
assert all(sorted(v)==[False,True] for v in pairs.values())
score=sum(g['candidate_points'] for g in games)/len(games)
result=dict(audit='PASS',games=16,wins=sum(g['candidate_points']==1 for g in games),draws=sum(g['candidate_points']==.5 for g in games),losses=sum(g['candidate_points']==0 for g in games),score=score,legal_plies=plies,
    cold_seconds={r['role']:r['metadata']['cold_seconds'] for r in workers},
    decision='NOMINATE confirmation' if score>=.6 else 'INCONCLUSIVE' if score>=.5 else 'REJECT promotion testing',
    scope='Used-family 16-game 500ms equal-wall addition screen; not full-clock or reliable Elo evidence.',plan_sha256=sha(h/'plan.json'),log_sha256=sha(h/'lane.jsonl'))
(h/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
