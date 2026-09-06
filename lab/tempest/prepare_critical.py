import json,io
from pathlib import Path
import chess,chess.pgn
H=Path(__file__).resolve().parent;R=H.parents[1]
rows=[]
for rnd,plies in [(32,[7,9,17,19]),(33,[5,7,33,35]),(34,[22,24,26,28])]:
    p=next((R/'Chess_results_day3').glob(f'*round-{rnd}-*.pgn'));g=chess.pgn.read_game(io.StringIO(p.read_text(encoding='utf-8-sig')));nodes=list(g.mainline())
    for ply in plies:
        b=g.board();clock={True:120000.,False:120000.};hist=[]
        for n in nodes[:ply]:
            if n.clock() is not None:clock[b.turn]=n.clock()*1000
            hist.append(n.move.uci());b.push(n.move)
        n=nodes[ply];player=g.headers['White' if b.turn else 'Black'];assert player!='Finlay Phillips'
        rows.append(dict(id=f'opp-r{rnd}-p{ply}',round=rnd,ply=ply,fen=b.fen(),start_fen=g.board().fen(),history_uci=hist,storm_colour='white' if b.turn else 'black',played_uci=n.move.uci(),played_san=b.san(n.move),time_left_ms=int(clock[b.turn]),player=player,split='discovery',group=f'day3-{rnd}',source_kind='opponent-targeted'))
(H/'opponent-critical.json').write_text(json.dumps(rows,indent=2))
(H/'opponent-critical-plan.json').write_text(json.dumps({'positions':len(rows),'selection':'Opposing turns immediately before/after known early and later own errors. Investigate whether their exploitation is actually inaccessible to v6. Selected discovery, not a new holdout.','budgets':[200000,1000000,1500],'mode':'nodes,nodes,wall; same direct native driver'},indent=2))
print(len(rows))
