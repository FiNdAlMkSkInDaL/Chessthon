"""Explicit real-history reply and mate-precedence tests for the frozen policy."""
import hashlib,json,sys
from pathlib import Path
import chess
HERE=Path(__file__).resolve().parent;source=HERE/'prototypes/tables_guard';sys.path.insert(0,str(source))
import syzygy_root as p,endgame_exact as e
proof=json.loads((HERE/'tablebase-verification.json').read_text())
tested=False
for row in proof['rollouts']:
    b=chess.Board(row['fen'])
    for move in list(b.legal_moves):
        b.push(move)
        if p.child_value(b)[0]==-2 and not b.is_checkmate():
            for reply in list(b.legal_moves):
                b.push(reply);key=b._transposition_key();eligible=not b.is_checkmate();b.pop()
                if eligible:
                    before=b.fen();assert p.child_value(b,{key:2})[0]==0 and b.fen()==before
                    tested=True;break
        b.pop()
        if tested:break
    if tested:break
assert tested
b=chess.Board('7k/6Q1/5K2/8/8/8/8/8 b - - 100 301');assert b.is_checkmate()
assert p.child_value(b,{b._transposition_key():2})==(-2,0,True)
b=chess.Board('8/k1P5/2K5/8/8/8/8/8 w - - 0 1')
assert e.choose_exact(b,allow_syzygy=False) is None and e.choose_exact(b)=='c7c8r'
b=chess.Board('7k/8/8/8/8/8/8/KR6 w - - 0 1')
assert e.choose_exact(b,allow_syzygy=False)==e._choose_original_dtm(b)
result=dict(audit='PASS',opponent_known_draw_reply=True,mate_before_fifty_repetition_cap=True,clock_guard_route_preserves_original_dtm=True,stalemate_avoiding_underpromotion=True,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(HERE/'table-boundaries.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
