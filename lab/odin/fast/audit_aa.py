"""Full-game A/A control must be deterministic and exactly50% per colour pair."""
import json,io,hashlib
from pathlib import Path
import chess.pgn
HERE=Path(__file__).resolve().parent
p=HERE/'isolation-aa.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()]
assert rows[-1]['type']=='summary'
games=[r for r in rows if r['type']=='game'];assert len(games)==4
for a,b in zip(games[::2],games[1::2]):
    assert a['opening_index']==b['opening_index'] and a['candidate_points']+b['candidate_points']==1
    for field in ('uci','depth','score','nodes'):
        assert [t[field] for t in a['telemetry']]==[t[field] for t in b['telemetry']],field
    pgn=chess.pgn.read_game(io.StringIO(a['pgn']));board=pgn.board()
    for m in pgn.mainline_moves():
        assert board.outcome(claim_draw=True) is None and m in board.legal_moves;board.push(m)
    assert board.outcome(claim_draw=True).result()==a['result']
report={'pass':True,'games':4,'pairs':2,'score':.5,'every_paired_move_depth_score_nodes_identical':True,'log_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(HERE/'aa-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
