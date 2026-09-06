"""Audit all frozen paired smoke games, including table-driven move routes."""
import json,io,hashlib,collections,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE))
import chess,chess.pgn
from review_v6_games import terminal
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    h=HERE/'exact-match';plan=json.loads((h/'plan-r2.json').read_text());games=[];workers=[];plies=0;routes=collections.Counter();pairs=collections.defaultdict(list)
    fpath=ROOT/'lab/odin/fast/generation-openings/screen.fen';fens=fpath.read_text().splitlines();assert sha(fpath)==plan['opening_sha256']
    for lane in ('a','b'):
        p=h/f'lane-{lane}.jsonl';rows=list(map(json.loads,p.read_text().splitlines()));assert rows[-1]['type']=='summary'
        assert rows[0]['think_ms']==100
        for r in rows:
            if r['type']=='worker':
                source=plan[r['role']];assert r['metadata']['source_hashes']==plan['sources'][source] and r['isolation']['pass'];workers.append(r)
            if r['type']!='game':continue
            g=chess.pgn.read_game(io.StringIO(r['pgn']));assert not g.errors;b=g.board();assert b.fen()==chess.Board(fens[r['opening_index']]).fen();color=r['candidate_colour']=='white';moves=list(g.mainline_moves());assert len(moves)==len(r['telemetry'])==r['plies']
            for m,t in zip(moves,r['telemetry']):
                assert terminal(b) is None and m in b.legal_moves and m.uci()==t['uci'];assert t['role']==('candidate' if b.turn==color else 'baseline');routes[t.get('route','unknown')]+=1;b.push(m);plies+=1
            result=terminal(b);assert result is not None and result.termination.name==r['termination'] and result.result()==r['result']==g.headers['Result']
            score=.5 if result.winner is None else float(result.winner==color);assert score==r['candidate_points'];pairs[r['opening_index']].append((color,score));games.append(r)
    assert len(games)==12 and len(workers)==4 and set(pairs)==set(plan['indices'])
    assert all(len(v)==2 and {c for c,_ in v}=={True,False} for v in pairs.values())
    for source,expected in plan['sources'].items():assert {p.name:sha(p) for p in (ROOT/source).iterdir() if p.is_file() and p.suffix in ('.py','.npz')}==expected
    points=sum(r['candidate_points'] for r in games);result=dict(audit='PASS',games=12,pairs=6,wins=sum(r['candidate_points']==1 for r in games),draws=sum(r['candidate_points']==.5 for r in games),losses=sum(r['candidate_points']==0 for r in games),score=points/12,legal_plies=plies,routes=dict(routes),smoke_score_guard_pass=points>=6,plan_sha256=sha(h/'plan-r2.json'),lanes={lane:sha(h/f'lane-{lane}.jsonl') for lane in ('a','b')},scope='100ms per search on two Linux CPU-pinned lanes. No full-game-clock or reliable Elo claim. No failed games excluded; initial attempt failed worker reset before any game.')
    (h/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
