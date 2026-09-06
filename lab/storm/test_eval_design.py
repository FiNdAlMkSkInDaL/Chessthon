"""Independent invariants for the isolated Storm positional evaluation spike.

Run with Python 3.12 and --engine dist/storm-eval-r3. These tests establish
geometry, perspective, and state integrity; they make no claim about Elo.
They deliberately test the correction separately from the existing PeSTO.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]


def board_with(chess, pieces, white_king="a1", black_king="h8"):
    board = chess.Board(None)
    board.set_piece_at(chess.parse_square(white_king), chess.Piece.from_symbol("K"))
    board.set_piece_at(chess.parse_square(black_king), chess.Piece.from_symbol("k"))
    for square, symbol in pieces.items():
        board.set_piece_at(chess.parse_square(square), chess.Piece.from_symbol(symbol))
    board.turn = chess.WHITE
    return board


def packed(c, board):
    from board_nb import from_fen
    return c.pack_pos(from_fen(board.fen(en_passant="fen")))


def test_pawn_attack_geometry(c, np, chess):
    rng = random.Random(51981)
    boards = [0, (1 << 64) - 1]
    boards += [1 << square for square in range(64)]
    boards += [rng.getrandbits(64) for _ in range(40)]
    for side in (0, 1):
        color = chess.WHITE if side == 0 else chess.BLACK
        for pawns in boards:
            expected = 0
            for square in chess.scan_forward(pawns):
                expected |= chess.BB_PAWN_ATTACKS[color][square]
            got = int(c.pawn_attack_union_nb(np.uint64(pawns), side))
            assert got == expected, ("pawn attack wrapping/direction", side, pawns, got, expected)


def test_passers(c, chess):
    def bonus(pieces, square="d5", white_king="a1", black_king="h8"):
        board = board_with(chess, pieces, white_king, black_king)
        bb, _, st = packed(c, board)
        value = tuple(map(int, c.passer_bonus_nb(bb, st, 0, chess.parse_square(square))))
        mirrored = board.mirror()
        m_bb, _, m_st = packed(c, mirrored)
        other = tuple(map(int, c.passer_bonus_nb(
            m_bb, m_st, 1, chess.square_mirror(chess.parse_square(square))
        )))
        assert value == other, ("passer color mirror", board.fen(), value, other)
        return value

    baseline = bonus({"d5": "P"})
    assert baseline[0] >= 0 and baseline[1] > 0, baseline
    for square in ("c6", "d6", "e6", "c7", "d7", "e7"):
        assert bonus({"d5": "P", square: "p"}) == (0, 0), ("enemy pawn ahead", square)
    for square in ("c4", "d4", "e4", "c5", "e5", "b6", "f6"):
        assert bonus({"d5": "P", square: "p"}) == baseline, ("irrelevant enemy pawn", square)

    for square, remote, adjacent in (("a5", "h6", "b6"), ("h5", "a6", "g6")):
        assert bonus({square: "P", remote: "p"}, square) == bonus({square: "P"}, square)
        assert bonus({square: "P", adjacent: "p"}, square) == (0, 0)
    assert bonus({"d5": "P", "d6": "P"}) == (0, 0), "trailing doubled passer credited"

    advances = [bonus({f"d{rank}": "P"}, f"d{rank}")[1] for rank in range(2, 8)]
    assert all(left <= right for left, right in zip(advances, advances[1:])), advances
    assert advances[-1] > advances[0], advances
    blocked = bonus({"d5": "P", "d6": "N"})
    unblocked = bonus({"d5": "P", "h2": "N"})
    assert blocked[1] < unblocked[1], ("occupied push square", blocked, unblocked)
    close_friend = bonus({"d5": "P"}, white_king="d4")
    close_enemy = bonus({"d5": "P"}, black_king="d7")
    assert close_friend[1] > baseline[1], ("friendly king support", close_friend, baseline)
    assert close_enemy[1] < baseline[1], ("enemy king blockade", close_enemy, baseline)
    return {"passer_rank_eg": advances, "passer_base": baseline}


def corpus(chess):
    fens = [
        chess.STARTING_FEN,
        "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
        "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
        "4k3/P7/8/8/8/8/7p/4K3 w - - 0 1",
        "7k/8/8/8/8/8/8/K7 w - - 0 1",
        "4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1",
        "4k3/8/8/8/8/8/8/2B1K1B1 w - - 0 1",
        "4k3/7q/8/8/8/Q7/8/4K3 w - - 0 1",
    ]
    diagnostic = ROOT / "lab" / "storm" / "day1_diagnostics.fen"
    if diagnostic.exists():
        fens.extend(diagnostic.read_text(encoding="utf-8").splitlines())
    rng = random.Random(310942)
    for root in fens[:4]:
        board = chess.Board(root)
        for ply in range(100):
            if board.is_game_over():
                break
            board.push(rng.choice(list(board.legal_moves)))
            if ply % 3 == 0:
                fens.append(board.fen())
    return [chess.Board(fen) for fen in dict.fromkeys(fens)]


def test_eval_invariants(c, np, chess, boards):
    corrections = []
    for board in boards:
        bb, mb, st = packed(c, board)
        before = (bb.copy(), mb.copy(), st.copy())
        terms = tuple(map(int, c.positional_terms_nb(bb, st)))
        correction = int(c.positional_eval_nb(bb, st))
        corrections.append(correction)
        assert int(c.evaluate_nb(bb, st, False)) == int(c.pesto_nb(bb, st, True)) + correction
        assert int(c.evaluate_nb(bb, st, True)) == int(c.kingless_nb(bb, st))
        assert all(np.array_equal(x, y) for x, y in zip(before, (bb, mb, st))), "eval mutates board"

        flipped = st.copy()
        flipped[c.SIDE] ^= np.uint64(1)
        assert tuple(map(int, c.positional_terms_nb(bb, flipped))) == terms
        assert int(c.positional_eval_nb(bb, flipped)) == -correction

        m_bb, _, m_st = packed(c, board.mirror())
        m_terms = tuple(map(int, c.positional_terms_nb(m_bb, m_st)))
        assert m_terms == tuple(-term for term in terms), ("raw color symmetry", board.fen(), terms, m_terms)
        assert int(c.positional_eval_nb(m_bb, m_st)) == correction, ("taper color symmetry", board.fen())

        h_bb, _, h_st = packed(c, board.transform(chess.flip_horizontal))
        h_terms = tuple(map(int, c.positional_terms_nb(h_bb, h_st)))
        assert h_terms == terms, ("horizontal geometry symmetry", board.fen(), terms, h_terms)

        max_phase = st.copy()
        promoted_phase = st.copy()
        max_phase[c.PHASE_ACC] = np.uint64(24)
        promoted_phase[c.PHASE_ACC] = np.uint64(96)
        assert c.positional_eval_nb(bb, max_phase) == c.positional_eval_nb(bb, promoted_phase)
    return {"positions": len(boards), "maximum_absolute_correction_cp": max(map(abs, corrections))}


def test_make_unmake_evaluation(c, np, chess, boards):
    from board_nb import move_uci
    moves = np.empty(c.MAX_MOVES, dtype=np.int32)
    scratch = np.empty(c.MAX_MOVES, dtype=np.int32)
    checked = 0
    # Special-move roots are tested exhaustively; ordinary roots use a sample.
    for index, board in enumerate(boards[:18]):
        bb, mb, st = packed(c, board)
        before = (bb.copy(), mb.copy(), st.copy())
        terms_before = c.positional_terms_nb(bb, st)
        n = c.gen_legal(bb, mb, st, moves, scratch)
        selected = moves[:n].copy() if index < 4 else moves[:min(n, 5)].copy()
        for move in selected:
            undo = np.zeros(7, dtype=np.uint64)
            child = board.copy()
            child.push(chess.Move.from_uci(move_uci(int(move))))
            c.make_nb(bb, mb, st, move, undo)
            expected_bb, expected_mb, expected_st = packed(c, child)
            assert all(np.array_equal(x, y) for x, y in zip(
                (bb, mb, st), (expected_bb, expected_mb, expected_st)
            )), ("incremental/fresh board mismatch", board.fen(), move_uci(int(move)))
            assert c.positional_terms_nb(bb, st) == c.positional_terms_nb(expected_bb, expected_st)
            assert c.evaluate_nb(bb, st, False) == c.evaluate_nb(expected_bb, expected_st, False)
            c.unmake_nb(bb, mb, st, move, undo)
            assert all(np.array_equal(x, y) for x, y in zip(before, (bb, mb, st)))
            assert c.positional_terms_nb(bb, st) == terms_before
            checked += 1
    return {"make_unmake_edges": checked}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=Path, default=ROOT / "dist" / "storm-eval-r3")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.engine.resolve()))
    import chess
    import numpy as np
    import core_nb as c

    test_pawn_attack_geometry(c, np, chess)
    result = test_passers(c, chess)
    boards = corpus(chess)
    result.update(test_eval_invariants(c, np, chess, boards))
    result.update(test_make_unmake_evaluation(c, np, chess, boards))
    result["engine"] = str(args.engine.resolve())
    result["note"] = "Evaluation invariants only; no playing-strength or speed claim."
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("EVAL DESIGN PASS " + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
