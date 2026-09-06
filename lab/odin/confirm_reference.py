"""Preserve individual score events and bound flags for key offline labels."""
import argparse,json,os,time
from datetime import datetime,timezone
from pathlib import Path
import chess,chess.engine
from lab.odin.reference_review import score_info,sha

def probe(engine,board,nodes,root_moves=None):
    events=[]
    with engine.analysis(board,chess.engine.Limit(nodes=nodes),game=object(),root_moves=root_moves) as analysis:
        for info in analysis:
            if 'score' in info:
                event=score_info(board,info)
                event.update(lowerbound=bool(info.get('lowerbound',False)),upperbound=bool(info.get('upperbound',False)))
                events.append(event)
        result=analysis.wait()
    exact=[v for v in events if not v['lowerbound'] and not v['upperbound'] and v['pv_uci'] and v['pv_uci'][0]==result.move.uci()]
    return {'final_bestmove':result.move.uci(),'last_score_event':events[-1],
            'last_exact_matching_bestmove':exact[-1] if exact else None,'score_events':events}

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--nodes',type=int,default=5000000);args=p.parse_args()
    wanted={('site-r16',24),('site-r16',30),('site-r17',59),('site-r17',64),('site-r18',21),('site-r20',38),('site-r21',33),('site-r22',35),('site-r22',72),('site-r23',28),('site-r23',30)}
    source=Path('lab/odin/reference-deep.jsonl')
    cases=[r for s in source.read_text().splitlines() if (r:=json.loads(s)).get('type')=='position' and (r['game_id'],r['move_number']) in wanted]
    assert len(cases)==len(wanted)
    exe=Path(os.environ['LOCALAPPDATA'])/'ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe'
    started=time.perf_counter()
    with chess.engine.SimpleEngine.popen_uci(str(exe)) as e,args.out.open('x',encoding='utf-8') as f:
        e.configure({'Threads':1,'Hash':128,'UCI_ShowWDL':True})
        def emit(r):f.write(json.dumps(r,allow_nan=False)+'\n');f.flush()
        emit({'type':'metadata','engine':e.id,'exe_sha256':sha(exe),'script_sha256':sha(Path(__file__)),'input_sha256':sha(source),'nodes_per_call':args.nodes,'hash_mb':128,'threads':1,'full_history':True,'clear_hash_each_call':True,'started_utc':datetime.now(timezone.utc).isoformat(),'note':'Individual score-event fields retained together. Finite-budget ordinary-chess analysis; not a proof under future competition claim-by-intended-move or cap semantics.'})
        for c in cases:
            b=chess.Board(c['start_fen'])
            for u in c['history_uci']:b.push_uci(u)
            assert b.fen()==c['fen'] and b.outcome(claim_draw=True) is None
            row={k:c[k] for k in ('game_id','ply','fen','start_fen','history_uci','storm_colour','played_uci','played_san','move_number')}
            row.update(type='confirmation',unrestricted=probe(e,b,args.nodes),played=probe(e,b,args.nodes,[chess.Move.from_uci(c['played_uci'])]))
            emit(row)
            print(json.dumps({'game':row['game_id'],'move':str(row['move_number'])+row['played_san'],'elapsed_s':round(time.perf_counter()-started,2)}),flush=True)
        emit({'type':'summary','cases':len(cases),'elapsed_s':time.perf_counter()-started,'finished_utc':datetime.now(timezone.utc).isoformat()})

if __name__=='__main__':main()
