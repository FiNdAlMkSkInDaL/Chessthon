"""Summarize completed offline review and export annotated site PGNs."""
import json, statistics, hashlib
from collections import defaultdict
from pathlib import Path
import chess,chess.engine,chess.pgn
from lab.odin.reference_review import games

def main():
    home=Path('lab/odin');path=home/'reference-screen.jsonl'
    raw=[json.loads(x) for x in path.read_text().splitlines()]
    assert raw[-1]['type']=='summary' and raw[-1]['positions']==6221
    by=defaultdict(list)
    for r in raw:
        if r['type']=='position':by[r['game_id']].append(r)
    assert len(by)==50
    summary=[];annotated=[];starts={}
    for gid,g,colour,source,digest in games():
        rows=by[gid];assert len(rows)==len(list(g.mainline_moves()))+1
        b=g.board();sign=1 if colour else -1;mistakes=[]
        for ply,node in enumerate(g.mainline()):
            a,z=rows[ply:ply+2]
            assert a['fen']==b.fen() and a['source_sha256']==digest
            if a['storm_turn'] and a['white_mate'] is None and z['white_mate'] is None and abs(a['white_cp'])<1500 and abs(z['white_cp'])<2000:
                mistakes.append({'ply':ply,'move':str(b.fullmove_number)+('.' if b.turn else '...')+b.san(node.move),'reference_storm_cp_before':sign*a['white_cp'],'reference_storm_cp_after':sign*z['white_cp'],'estimated_drop_cp':sign*(a['white_cp']-z['white_cp']),'preferred_san':a['pv_san'][:8],'fen':a['fen']})
            b.push(node.move);assert b.fen()==z['fen']
            if gid.startswith('site'):
                if z.get('terminal'):
                    node.comment+=' Reference terminal: '+z['terminal']+'.'
                else:
                    val=chess.engine.Mate(z['white_mate']) if z['white_mate'] is not None else chess.engine.Cp(z['white_cp'])
                    node.set_eval(chess.engine.PovScore(val,chess.WHITE),z.get('depth'))
        summary.append({'game_id':gid,'result':g.headers['Result'],'storm_colour':'white' if colour else 'black','plies':len(rows)-1,'reference_initial_white_cp':rows[0]['white_cp'],'screen_largest_storm_drops':sorted(mistakes,key=lambda x:x['estimated_drop_cp'],reverse=True)[:8]})
        if gid.startswith('holdout'):starts[rows[0]['fen']]=rows[0]['white_cp']
        else:
            g.headers['Annotator']='Offline Stockfish 19 screening, 100k nodes per position; finite-budget estimates, not proofs'
            g.comment+=' Original game clocks preserved. Evaluations are independent after-position screening estimates; use confirmed diagnostics for conclusions.'
            annotated.append(str(g))
    out={'games':summary,'positions':6221,'played_plies':6171,'native_unique_starts':len(starts),'native_start_screen':{'abs_over_100_cp':sum(abs(v)>100 for v in starts.values()),'abs_over_200_cp':sum(abs(v)>200 for v in starts.values()),'max_abs_cp':max(abs(v) for v in starts.values()),'median_abs_cp':statistics.median(abs(v) for v in starts.values()),'starts':[{'fen':k,'white_cp':v} for k,v in starts.items()]},'limitations':['100k-node site / 50k-node native screens; adjacent-root score changes are estimates, not verified move loss.','Screen and first deep pass aggregate UCI info and did not preserve bound flags; do not treat their reported depth/score/PV as a certified complete exact event.','Confirm key positions using reference-confirmed.jsonl streamed score events or retained tablebase evidence.','External engine does not implement the competition mandatory intended-move claim or 600-ply cap inside its own search.','These reviewed positions are development diagnostics, not an unseen future holdout.'],'screen_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (home/'reference-summary.json').write_text(json.dumps(out,indent=2)+'\n')
    (home/'Storm-day2-reference-annotated.pgn').write_text('\n\n'.join(annotated)+'\n')
    print(json.dumps({'games':len(summary),'positions':6221,'native_start_screen':out['native_start_screen']},indent=2))

if __name__=='__main__':main()
