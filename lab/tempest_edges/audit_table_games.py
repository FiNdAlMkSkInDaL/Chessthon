"""Check every actual four-piece table decision from the completed screens."""
import collections,hashlib,io,json,sys
from pathlib import Path
import chess,chess.pgn
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'prototypes/tables_guard'))
from syzygy_root import child_value
decisions=[]
for name in ('bundle','tables'):
    rows=[json.loads(s) for s in (HERE/f'match-{name}/lane.jsonl').read_text().splitlines()]
    for r in rows:
        if r['type']!='game':continue
        g=chess.pgn.read_game(io.StringIO(r['pgn']));b=g.board();seen=collections.Counter({b._transposition_key():1})
        for ply,(move,t) in enumerate(zip(g.mainline_moves(),r['telemetry'])):
            if t['role']=='candidate' and t['route']=='exact' and b.occupied.bit_count()==4:
                values={}
                for alternative in list(b.legal_moves):
                    b.push(alternative)
                    try:values[alternative.uci()]=-child_value(b,seen)[0]
                    finally:b.pop()
                assert values[move.uci()]==max(values.values()),(name,r['game'],ply,b.fen(),move,values)
                decisions.append(dict(screen=name,game=r['game'],ply=ply,fen=b.fen(),uci=move.uci(),value=values[move.uci()]))
            b.push(move);seen[b._transposition_key()]+=1
result=dict(audit='PASS',decisions=len(decisions),outcomes=dict(collections.Counter(r['value'] for r in decisions)),rows=decisions,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Every observed four-piece table decision preserved the best available rule-adjusted child value under actual replay history. This does not estimate general playing strength.')
(HERE/'actual-table-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
