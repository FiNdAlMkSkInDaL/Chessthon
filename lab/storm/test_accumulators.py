"""PeSTO accumulator parity through random legal games and special moves."""
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "storm"))
import chess
import numpy as np
import core_nb as c
from board_nb import from_fen


def main():
    rng = random.Random(49201)
    roots = [chess.STARTING_FEN,
             "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
             "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
             "4k3/P7/8/8/8/8/7p/4K3 w - - 0 1"]
    visited = 0
    for fen in roots:
        board = chess.Board(fen)
        bb, mb, st = c.pack_pos(from_fen(fen))
        saved = []
        for ply in range(150):
            assert int(c.pesto_nb(bb, st, True)) == int(c.pesto_reference_nb(bb, st, True))
            exp_bb, exp_mb, exp_st = c.pack_pos(from_fen(board.fen(en_passant="fen")))
            assert np.array_equal(bb, exp_bb) and np.array_equal(mb, exp_mb)
            assert np.array_equal(st, exp_st), (fen, ply, st, exp_st)
            moves = np.empty(256, dtype=np.int32)
            scratch = np.empty(256, dtype=np.int32)
            before = (bb.copy(), mb.copy(), st.copy())
            n = c.gen_legal(bb, mb, st, moves, scratch)
            assert all(np.array_equal(x,y) for x,y in zip((bb,mb,st), before))
            visited += 1
            if n == 0:
                break
            move = int(moves[rng.randrange(n)])
            from board_nb import move_uci
            py_move = chess.Move.from_uci(move_uci(move))
            assert py_move in board.legal_moves
            undo = np.zeros(7, dtype=np.uint64)
            c.make_nb(bb, mb, st, move, undo)
            saved.append((move, undo, before))
            board.push(py_move)
        for move, undo, before in reversed(saved):
            c.unmake_nb(bb, mb, st, move, undo)
            assert all(np.array_equal(x,y) for x,y in zip((bb,mb,st), before))
    # Check EVERY promotion, castle and EP from the diagnostic roots.
    for fen in roots[1:]:
        bb,mb,st = c.pack_pos(from_fen(fen))
        moves=np.empty(256,dtype=np.int32); scratch=moves.copy()
        n=c.gen_legal(bb,mb,st,moves,scratch)
        for move in moves[:n]:
            before=(bb.copy(),mb.copy(),st.copy()); undo=np.zeros(7,dtype=np.uint64)
            c.make_nb(bb,mb,st,move,undo)
            assert c.pesto_nb(bb,st,True)==c.pesto_reference_nb(bb,st,True)
            c.unmake_nb(bb,mb,st,move,undo)
            assert all(np.array_equal(x,y) for x,y in zip((bb,mb,st),before))
    print(f"ACCUMULATORS PASS positions={visited} all undo states exact")


if __name__ == "__main__":
    main()
