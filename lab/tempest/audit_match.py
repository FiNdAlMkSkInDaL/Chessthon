import json,io,hashlib,collections
from pathlib import Path
import chess,chess.pgn
from rule_probe import current
H=Path(__file__).resolve().parent;R=H.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    plan=json.loads((H/'match/plan.json').read_text());rows=[json.loads(s) for s in (H/'match/games.jsonl').read_text().splitlines()];assert rows[-1]['type']=='summary';games=[r for r in rows if r['type']=='game'];assert len(games)==12
    fens=(R/plan['openings']).read_text().splitlines();assert sha(R/plan['openings'])==plan['opening_sha256'];pairs=collections.defaultdict(list);plies=0;seconds=[];workers=[]
    for r in rows:
        if r['type']!='worker':continue
        meta=r['metadata'];role=r['role'];assert meta['source_hashes']==plan[role+'_hashes'];assert r['isolation']['pass'];workers.append(dict(role=role,source=meta['source'],cold_seconds=meta['cold_seconds'],isolation=True))
    assert len(workers)==2
    for g in games:
        pgn=chess.pgn.read_game(io.StringIO(g['pgn']));assert not pgn.errors;b=pgn.board();assert b.fen()==chess.Board(fens[g['opening_index']]).fen();moves=list(pgn.mainline_moves());assert len(moves)==len(g['telemetry'])==g['plies']
        candidate=g['candidate_colour']=='white'
        for m,t in zip(moves,g['telemetry']):
            assert current(b) is None and m in b.legal_moves
            assert m.uci()==t['uci'];assert t['role']==('candidate' if b.turn==candidate else 'baseline');assert t['seconds']>=0;seconds.append(t['seconds']);b.push(m);plies+=1
        assert current(b)==g['termination'],(current(b),g['termination'])
        outcome=b.outcome();result=outcome.result() if outcome else '1/2-1/2';assert result==g['result']==pgn.headers['Result']
        score=.5 if result=='1/2-1/2' else float((result=='1-0')==candidate);assert score==g['candidate_points'];pairs[g['opening_index']].append((candidate,score))
    assert set(pairs)==set(plan['indices']) and all(len(v)==2 and {c for c,_ in v}=={True,False} for v in pairs.values())
    for role in ('baseline','candidate'):
        source=R/'odin_v6' if role=='baseline' else H/'prototypes/pesto_only';assert {p.name:sha(p) for p in source.glob('*.py')}==plan[role+'_hashes']
    points=sum(g['candidate_points'] for g in games);w=sum(g['candidate_points']==1 for g in games);d=sum(g['candidate_points']==.5 for g in games);l=sum(g['candidate_points']==0 for g in games)
    result=dict(audit='PASS',games=12,pairs=6,wins=w,draws=d,losses=l,points=points,score=points/12,legal_plies=plies,workers=workers,current_referee_commit=plan['referee_commit'],plan_sha256=sha(H/'match/plan.json'),log_sha256=sha(H/'match/games.jsonl'),pair_scores={str(k):sum(x[1] for x in v)/2 for k,v in pairs.items()},terminations=dict(collections.Counter(g['termination'] for g in games)),max_observed_move_seconds=max(seconds),followup_criterion_pass=points/12>=.6,verdict='Reject PeSTO-only as first build; selected-root gain did not carry into this small development screen. No reliable Elo estimate or full-clock flag claim.',scope='100ms search allowance per move, actual get_move, persistent state within game, full reset between games, current terminal rules. Not120+0.5 game clock; no native Linux import or submission gate.')
    (H/'match/summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
