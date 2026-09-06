import io
import json
from pathlib import Path

import chess.pgn

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
source=ROOT/'lab/odin/native_release/odin-fixed-r1/development-partial.jsonl'
rows=[json.loads(s) for s in source.read_text().splitlines()]
row=next(r for r in rows if r.get('type')=='game' and r['game']==1)
(HERE/'fixed-r1-game1-source.json').write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8')
(HERE/'fixed-r1-game1.pgn').write_text(row['pgn']+'\n',encoding='utf-8')
deep=[json.loads(s) for s in (HERE/'fixed-r1-game1-deep.jsonl').read_text().splitlines()]
bounds=[json.loads(s) for s in (HERE/'fixed-r1-game1-critical-bounds.jsonl').read_text().splitlines()]
reference={r['ply']:r for r in deep if r.get('type')=='position'}
reference.update({r['ply']:r for r in bounds if r.get('type')=='position'})
game=chess.pgn.read_game(io.StringIO(row['pgn']))
board=game.board()
history=[]
diagnostics=[]
for ply,move in enumerate(game.mainline_moves()):
    if ply in reference:
        result=reference[ply]
        diagnostics.append({'id':f'fixed-r1-development-g1-ply{ply}',
                            'start_fen':game.board().fen(),'history_uci':history.copy(),
                            'fen':board.fen(),'absolute_ply':board.ply(),
                            'played_uci':move.uci(),'recorded_time_ms':result['timing']['elapsed_ms'],
                            'recorded_time_left_ms':result['timing']['time_left_ms'],
                            'reference_1m':result,'scope':'Development diagnosis; never ship move labels or pool with holdout.'})
    history.append(move.uci())
    board.push(move)
(HERE/'fixed-r1-diagnostic-roots.json').write_text(json.dumps(diagnostics,indent=2)+'\n',encoding='utf-8')
for ply in (0,6,16,42,44,62):
    r=reference[ply]
    print(json.dumps({'move':str(r['move_number'])+'.'+r['played_san'],'best':r['pv_san'][:3],
                      'best_cp':r['white_cp'],'played_cp':r['played_root']['white_cp'],
                      'best_bound':(r.get('lowerbound'),r.get('upperbound')),
                      'played_bound':(r['played_root'].get('lowerbound'),r['played_root'].get('upperbound'))}))
