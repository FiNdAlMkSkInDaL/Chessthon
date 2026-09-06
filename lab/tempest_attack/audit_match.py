"""Independent replay and identity audit of every declared development game."""
import json,hashlib,io,collections,sys,argparse
from pathlib import Path
import chess,chess.pgn
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'lab/tempest_build'))
from review_v6_games import terminal
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='match');args=ap.parse_args();assert args.name in ('match','match-lmr','match-policy')
    h=HERE/args.name;plan=json.loads((h/'plan.json').read_text());games=[];workers=[];pairs=collections.defaultdict(list);plies=0
    opening=ROOT/'lab/odin/fast/generation-openings/screen.fen';assert sha(opening)==plan['opening_sha256']
    fens=[s for s in opening.read_text().splitlines() if s.strip() and not s.startswith('#')]
    for name,digest in plan['helpers_sha256'].items():assert sha(h/name)==digest
    for lane,indices in [('a',[0,1,2,3]),('b',[4,5,6,7])]:
        rows=list(map(json.loads,(h/f'lane-{lane}.jsonl').read_text().splitlines()))
        assert rows[-1]['type']=='summary' and rows[-1]['games']==8
        assert rows[0]['indices']==indices and rows[0]['think_ms']==plan['think_ms'] and rows[0]['openings_sha256']==sha(opening)
        for r in rows:
            if r['type']=='worker':
                assert r['metadata']['source_hashes']==plan['sources'][plan[r['role']]]
                assert r['metadata']['worker_sha256']==plan['helpers_sha256']['clock_worker.py']
                assert r['isolation']['pass'];workers.append(r)
            if r['type']!='game':continue
            assert r['opening_index'] in indices
            g=chess.pgn.read_game(io.StringIO(r['pgn']));assert not g.errors
            b=g.board();assert b.fen()==chess.Board(fens[r['opening_index']]).fen()
            moves=list(g.mainline_moves());assert len(moves)==r['plies']==len(r['telemetry'])
            own=r['candidate_colour']=='white'
            for m,t in zip(moves,r['telemetry']):
                assert terminal(b) is None and m in b.legal_moves and m.uci()==t['uci']
                assert t['role']==('candidate' if b.turn==own else 'baseline')
                assert t['seconds']>=0;b.push(m);plies+=1
            result=terminal(b);assert result is not None
            assert result.result()==r['result']==g.headers['Result'] and result.termination.name==r['termination']
            points=.5 if result.winner is None else float(result.winner==own)
            assert points==r['candidate_points'];pairs[r['opening_index']].append((own,points));games.append(r)
    assert len(games)==16 and len(workers)==4 and set(pairs)==set(plan['indices'])
    assert all(len(v)==2 and {c for c,_ in v}=={True,False} for v in pairs.values())
    for source,expected in plan['sources'].items():
        assert {p.name:sha(p) for p in (ROOT/source).iterdir() if p.is_file() and p.suffix in ('.py','.npz')}==expected
    score=sum(g['candidate_points'] for g in games)/len(games)
    result=dict(audit='PASS',games=len(games),wins=sum(g['candidate_points']==1 for g in games),draws=sum(g['candidate_points']==.5 for g in games),losses=sum(g['candidate_points']==0 for g in games),score=score,legal_plies=plies,
      candidate_cold_imports=[w['metadata']['cold_seconds'] for w in workers if w['role']=='candidate'],
      decision='MERITS independent confirmation' if score>=.6 else 'INCONCLUSIVE; no promotion' if score>=.5 else 'REJECT promotion testing',
      scope=f"16 development games at equal {plan['think_ms']}ms search allowance; complete pairs, source/reset/legal audit. Not full-clock or reliable Elo evidence.",
      plan_sha256=sha(h/'plan.json'),logs={lane:sha(h/f'lane-{lane}.jsonl') for lane in ('a','b')})
    (h/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
