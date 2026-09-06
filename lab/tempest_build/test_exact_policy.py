"""Current-rule complete conversions and clock boundaries, plus negative scope."""
import os,sys,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tempest_exact'))
import numpy as np,chess
import endgame_exact as e
def board_for(idx,pt):
    side=idx//262144;rest=idx%262144;ak=rest//4096;m=rest//64%64;dk=rest%64
    b=chess.Board(None);b.set_piece_at(ak,chess.Piece(chess.KING,True));b.set_piece_at(m,chess.Piece(pt,True));b.set_piece_at(dk,chess.Piece(chess.KING,False));b.turn=not side;return b
start=time.perf_counter();games=[];worst=0.;rng=np.random.default_rng(1235)
for pt in (chess.QUEEN,chess.ROOK):
    tab=e._TABLES[pt]
    for idx in rng.choice(np.flatnonzero((tab<255)&(tab>0)),160,replace=False):
        for mirror in (False,True):
            b=board_for(int(idx),pt)
            if mirror:b=b.mirror()
            attacker=not mirror;distance=int(tab[idx]);seen={};n=0
            while not b.is_game_over() and not b.is_repetition(3) and not b.is_fifty_moves():
                key=b._transposition_key();seen[key]=seen.get(key,0)+1
                t=time.perf_counter();u=e.choose_exact(b,seen);worst=max(worst,time.perf_counter()-t)
                assert u and chess.Move.from_uci(u) in b.legal_moves
                b.push_uci(u);n+=1;assert n<=distance
            assert b.is_checkmate() and b.outcome().winner==attacker and n==distance
            games.append(dict(piece=pt,mirrored=mirror,mate_plies=n))
# Verify exact boundary: mate on the 100th halfmove or absolute ply 600 wins.
boundary=[]
for pt in (chess.QUEEN,chess.ROOK):
    tab=e._TABLES[pt]
    for d in (1,3,5,9):
        idx=int(np.flatnonzero(tab[:262144]==d)[0]);b=board_for(idx,pt);b.halfmove_clock=100-d
        for _ in range(d):b.push_uci(e.choose_exact(b))
        assert b.is_checkmate() and b.halfmove_clock==100;boundary.append([pt,d,'fifty_mate'])
        b=board_for(idx,pt).mirror();b.fullmove_number=(600-d)//2+1
        assert b.ply()==600-d
        for _ in range(d):b.push_uci(e.choose_exact(b))
        assert b.is_checkmate() and b.ply()==600;boundary.append([pt,d,'absolute_cap_mate'])
# Preserve board and return None for all ordinary / unsupported positions.
for fen in (chess.STARTING_FEN,'8/8/8/8/8/6k1/8/KB6 w - - 0 1','8/8/8/8/8/6k1/8/KP6 w - - 0 1'):
    b=chess.Board(fen);assert e.choose_exact(b) is None and b.fen()==fen
# Exposed major can be captured for a draw by the defending side.
b=chess.Board('8/8/8/8/8/8/kR6/7K b - - 0 1');u=e.choose_exact(b);b.push_uci(u);assert b.is_insufficient_material()
result=dict(pass_all=True,complete_conversions=len(games),total_plies=sum(g['mate_plies'] for g in games),max_policy_ms=worst*1000,seconds=time.perf_counter()-start,boundaries=boundary,scope='640 independently started exact-policy-versus-exact-policy conversions; not strength games against v6.')
(HERE/'three-piece/policy-test.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
