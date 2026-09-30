"""Follow up the earlier advantage loss in the native rook ending."""
import json,os,time
from pathlib import Path
from datetime import datetime,timezone
import chess,chess.engine
from lab.odin.confirm_reference import probe
from lab.odin.reference_review import sha

def main():
    home=Path('lab/odin');source=home/'reference-screen.jsonl'
    cases=[r for s in source.read_text().splitlines() if (r:=json.loads(s)).get('game_id')=='holdout-a-g12-o165' and r.get('storm_turn') and r.get('move_number') in (48,49,50,51)]
    assert len(cases)==4
    exe=Path('stockfish')
    start=time.perf_counter()
    with chess.engine.SimpleEngine.popen_uci(str(exe)) as e,(home/'reference-conversion-confirmed.jsonl').open('x',encoding='utf-8') as f:
        e.configure({'Threads':1,'Hash':128,'UCI_ShowWDL':True})
        def emit(r):f.write(json.dumps(r,allow_nan=False)+'\n');f.flush()
        emit({'type':'metadata','nodes_per_call':5000000,'threads':1,'hash_mb':128,'engine':e.id,'exe_sha256':sha(exe),'input_sha256':sha(source),'script_sha256':sha(Path(__file__)),'probe_script_sha256':sha(Path('lab/odin/confirm_reference.py')),'full_history':True,'clear_hash_each_call':True,'started_utc':datetime.now(timezone.utc).isoformat(),'note':'Post-screen targeted conversion check; finite-budget ordinary-chess estimates, streamed UCI event bounds retained.'})
        for c in cases:
            b=chess.Board(c['start_fen'])
            for u in c['history_uci']:b.push_uci(u)
            assert b.fen()==c['fen']
            r={k:c[k] for k in ('game_id','ply','fen','start_fen','history_uci','storm_colour','played_uci','played_san','move_number','source','source_sha256')}
            r.update(type='confirmation',unrestricted=probe(e,b,5000000),played=probe(e,b,5000000,[chess.Move.from_uci(c['played_uci'])]))
            assert r['played']['final_bestmove']==r['played_uci']
            emit(r)
            a=r['unrestricted']['last_exact_matching_bestmove'];z=r['played']['last_exact_matching_bestmove']
            print(json.dumps({'move':str(r['move_number'])+r['played_san'],'best_black_cp':-a['white_cp'],'played_black_cp':-z['white_cp'],'pv':a['pv_san'][:8],'elapsed_s':time.perf_counter()-start}),flush=True)
        emit({'type':'summary','cases':4,'elapsed_s':time.perf_counter()-start,'finished_utc':datetime.now(timezone.utc).isoformat()})

if __name__=='__main__':main()
