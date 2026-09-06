"""Replay every fixed-search-time development game and bind its source identity."""
import argparse,hashlib,io,json
from pathlib import Path
import chess,chess.pgn
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--openings',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('logs',nargs='+',type=Path);args=ap.parse_args()
fens=args.openings.read_text().splitlines();digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected={'candidate':{p.name:digest(p) for p in args.candidate.glob('*.py')},'baseline':{p.name:digest(p) for p in (ROOT/'odin_submission').glob('*.py')}}
coverage=set();games=[];lanes=[]
for path in args.logs:
    rows=[json.loads(s) for s in path.read_text().splitlines()];plan=rows[0];assert plan['type']=='plan'
    assert plan['openings_sha256']==digest(args.openings)
    workers={r['role']:r for r in rows if r['type']=='worker'};assert set(workers)==set(expected)
    for role,w in workers.items():
        assert w['isolation']['pass'] and w['metadata']['source_hashes']==expected[role]
        assert w['metadata']['silent_native_fallback_rejected'] and not w['metadata']['readiness_override']
    modes=[r for r in rows if r['type']=='clock_mode'];assert len(modes)==2
    assert all(r['hard_ms']==plan['think_ms'] and r['soft_ms']==plan['think_ms']*.9 for r in modes)
    lane_games=[r for r in rows if r['type']=='game'];assert len(lane_games)==2*len(plan['indices'])
    assert rows[-1]['type']=='summary' and rows[-1]['games']==len(lane_games)
    for row in lane_games:
        identity=(row['opening_index'],row['candidate_colour']);assert identity not in coverage;coverage.add(identity)
        assert row['opening_index'] in plan['indices']
        g=chess.pgn.read_game(io.StringIO(row['pgn']));assert not g.errors
        b=chess.Board(fens[row['opening_index']]);assert b.fen()==g.board().fen()
        moves=list(g.mainline_moves());assert len(moves)==row['plies']==len(row['telemetry'])
        for move,t in zip(moves,row['telemetry']):
            assert b.outcome(claim_draw=True) is None and b.ply()<600
            assert move in b.legal_moves and move.uci()==t['uci']
            expected_role='candidate' if b.turn==(row['candidate_colour']=='white') else 'baseline'
            assert t['role']==expected_role and t['nodes']>=0 and t['seconds']>=0
            b.push(move)
        outcome=b.outcome(claim_draw=True)
        if outcome is None:assert b.ply()>=600;result='1/2-1/2';termination='PLY_CAP'
        else:result=outcome.result();termination=outcome.termination.name
        assert row['result']==result and row['termination']==termination
        points=.5 if result=='1/2-1/2' else float((result=='1-0')==(row['candidate_colour']=='white'))
        assert row['candidate_points']==points;games.append(row)
    lanes.append({'path':str(path),'sha256':digest(path),'games':len(lane_games),'think_ms':plan['think_ms']})
assert {i for i,c in coverage}==set(range(len(fens)))
result={'pass':True,'games':len(games),'wins':sum(g['candidate_points']==1 for g in games),'draws':sum(g['candidate_points']==.5 for g in games),'losses':sum(g['candidate_points']==0 for g in games),'score':sum(g['candidate_points'] for g in games)/len(games),'plies':sum(g['plies'] for g in games),'source_hashes':expected,'lanes':lanes,'scope':'Development screen with equal fixed search-time allowance per move. Not full competition clocks, not unbiased promotion evidence. Final112-game untouched paired-opening full-clock match remains required.'}
args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('source_hashes','lanes')}))
