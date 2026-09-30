"""Bounded offline follow-up for r4's changed move at the development root."""
import hashlib
import json
import os
from pathlib import Path
import sys

import chess
import chess.engine

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.odin.development_review.review import analyse,pin_cpu4
HERE=Path(__file__).resolve().parent

pin_cpu4(os.getpid())
case=next(c for c in json.loads((HERE/'fixed-r1-diagnostic-roots.json').read_text()) if c['id'].endswith('ply44'))
board=chess.Board(case['start_fen'])
for uci in case['history_uci']:
    board.push_uci(uci)
assert board.fen()==case['fen']
exe=Path('stockfish')
with chess.engine.SimpleEngine.popen_uci(str(exe)) as engine:
    pin_cpu4(engine.transport.get_pid())
    engine.configure({'Threads':1,'Hash':128,'UCI_ShowWDL':True})
    result={'id':case['id'],'fen':board.fen(),'history_uci':case['history_uci'],
            'engine':engine.id,'engine_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
            'cpu':4,'threads':1,'nodes_per_move':1000000,'alternatives':{}}
    for uci in ('c3e5','a4b5'):
        move=chess.Move.from_uci(uci)
        assert move in board.legal_moves
        result['alternatives'][uci]=analyse(engine,board,1000000,[move])
    (HERE/'r4-be5-reference.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['alternatives']),flush=True)
