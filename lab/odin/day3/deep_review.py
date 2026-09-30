"""Finite independent same-root best/played-move comparisons; offline only."""
import json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from lab.odin.development_review.review import pin_cpu4
from lab.odin.new_games.review_new import reference
import chess,chess.engine
pin_cpu4(os.getpid(),4)
exe=Path('stockfish')
roots=json.loads((HERE/'selected-roots.json').read_text())
with chess.engine.SimpleEngine.popen_uci(str(exe)) as e,(HERE/'deep-reference.jsonl').open('x',encoding='utf-8') as out:
    e.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
    for r in roots:
        b=chess.Board(r['start_fen'])
        for uci in r['history_uci']:b.push_uci(uci)
        assert b.fen()==r['fen']
        best=reference(e,b,2000000)
        move=chess.Move.from_uci(r['played_uci']);played=reference(e,b,2000000,[move])
        sign=1 if r['storm_colour']=='white' else -1
        row={'id':r['id'],'round':r['round'],'ply':r['ply'],'move_number':b.fullmove_number,'colour':r['storm_colour'],'played_san':r['played_san'],
             'best':best,'played':played,'best_own_cp':sign*best['white_cp'],'played_own_cp':sign*played['white_cp'],
             'loss_cp':sign*(best['white_cp']-played['white_cp']),'time_left_ms':r['time_left_ms'],'scope':'2M nodes per same-root search, exact completed iteration; finite diagnostic reference, not chess truth or training.'}
        out.write(json.dumps(row)+'\n');out.flush();print(json.dumps(row),flush=True)
