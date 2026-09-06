"""Deepen earliest consequential and later recoverable screen errors per game."""
import json,sys,io
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(R))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(6)['applied']
import chess,chess.pgn,chess.engine
from lab.odin.new_games.review_new import reference
rows=[json.loads(s) for s in (H/'reference-games.jsonl').read_text().splitlines()];rows=[r for r in rows if r.get('type')=='screen']
manifest={m['game_id']:m for m in json.loads((H/'public/games.json').read_text())}
chosen=[]
for gid in dict.fromkeys(r['game_id'] for r in rows):
    eligible=[r for r in rows if r['game_id']==gid and r['loss_cp']>=80 and r['best']['pv_uci'][0]!=r['uci'] and abs(r['best']['white_cp'])<400 and r['best'].get('white_mate') is None and r['played'].get('white_mate') is None]
    if not eligible:continue
    first=min(eligible,key=lambda r:r['ply']);chosen.append(first)
    later=[r for r in eligible if r['ply']>first['ply']+3]
    if later:chosen.append(max(later,key=lambda r:r['loss_cp']))
(H/'public-deep-plan.json').write_text(json.dumps({'keys':[r['key'] for r in chosen],'nodes':2000000,'selection':'Earliest >=80cp non-mate screen divergence, then largest later recoverable opportunity; ignore same-move reference disagreement.'},indent=2))
exe='C:/Users/finla/AppData/Local/ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe'
with chess.engine.SimpleEngine.popen_uci(exe) as e,(H/'public-deep.jsonl').open('x') as out:
    e.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
    for r in chosen:
        m=manifest[r['game_id']];g=chess.pgn.read_game(io.StringIO((H/m['pgn']).read_text()));b=g.board();hist=[]
        for n in list(g.mainline())[:r['ply']]:b.push(n.move);hist.append(n.move.uci())
        best=reference(e,b,2000000);played=reference(e,b,2000000,[chess.Move.from_uci(r['uci'])]);sign=1 if b.turn else -1
        out.write(json.dumps(dict(key=r['key'],game_id=r['game_id'],ply=r['ply'],player=r['player'],san=r['san'],fen=b.fen(),start_fen=g.board().fen(),history_uci=hist,best=best,played=played,loss_cp=sign*(best['white_cp']-played['white_cp']),screen_loss_cp=r['loss_cp'],clock_before_ms=r['clock_before_ms']))+'\n');out.flush()
print('done',len(chosen))
