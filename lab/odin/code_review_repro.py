"""Lightweight source-isolated reproductions; deliberately never imports core_nb."""
from __future__ import annotations
import ast
import json
from pathlib import Path
import sys
import numpy as np
import chess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "storm"))
from board_nb import from_fen
from movegen_nb import bishop_attacks, rook_attacks, generate_legal, move_uci
from tables_nb import PAWN_ATK, KNIGHT_ATK, KING_ATK
import history
from storm_clock import allocation, moves_to_go


def source_functions():
    tree = ast.parse((ROOT / "storm/core_nb.py").read_text())
    wanted = {"m_from", "m_to", "m_promo", "m_ep", "bit", "lva", "see_nb", "is_repeat"}
    body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            node.decorator_list = []
            body.append(node)
    namespace = {"np": np, "PAWN_A": np.array(PAWN_ATK, dtype=np.uint64),
                 "KNIGHT_A": np.array(KNIGHT_ATK, dtype=np.uint64),
                 "KING_A": np.array(KING_ATK, dtype=np.uint64),
                 "SEE_V": np.array((100, 300, 300, 500, 900, 20000)),
                 "KEY": 8, "SIDE": 3, "OCC": 2,
                 "lsb": lambda bb: (int(bb) & -int(bb)).bit_length() - 1,
                 "bishop_att": lambda sq, occ: np.uint64(bishop_attacks(int(sq), int(occ))),
                 "rook_att": lambda sq, occ: np.uint64(rook_attacks(int(sq), int(occ)))}
    exec(compile(ast.Module(body=body, type_ignores=[]), "core_nb.source_isolated", "exec"), namespace)
    return namespace


def run():
    funcs = source_functions()
    rows = []
    for kind, fen, uci in [
        ("illegal_king_recapture", "5k2/6p1/8/8/8/8/1B6/4K1R1 w - - 0 1", "g1g7"),
        ("pinned_bishop_recapture", "4k3/4b3/3p4/2B5/8/8/8/4R1K1 w - - 0 1", "c5d6"),
    ]:
        board = chess.Board(fen)
        assert board.is_valid()
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves
        pos = from_fen(fen)
        packed = next(m for m in generate_legal(pos) if move_uci(m) == uci)
        state = np.zeros(12, dtype=np.uint64)
        state[2] = pos.occ
        state[3] = pos.side
        score = int(funcs["see_nb"](np.array(pos.bb, dtype=np.uint64),
                                   np.array(pos.mb, dtype=np.int8), state, packed))
        board.push(move)
        recaptures = [m.uci() for m in board.legal_moves if m.to_square == move.to_square]
        assert not recaptures
        rows.append({"kind": kind, "fen": fen, "move": uci,
                     "source_isolated_see": score, "legal_recaptures": recaptures,
                     "gives_check": board.is_check(), "captured_value": 100})

    ep = chess.Board()
    ep.push_uci("e2e4")
    fen_with = ep.fen(en_passant="fen")
    fen_without = ep.fen()
    assert chess.Board(fen_with)._transposition_key() == chess.Board(fen_without)._transposition_key()
    ep_record = {"fen_with_ep": fen_with, "fen_without_ep": fen_without,
                 "referee_keys_equal": True,
                 "storm_keys_equal": from_fen(fen_with).key == from_fen(fen_without).key}
    fifty_fen = "6k1/8/8/8/8/8/8/R5K1 w - - {halfmove} 1"
    fifty_record = {"counter_values": [0, 98],
                    "storm_keys_equal": from_fen(fifty_fen.format(halfmove=0)).key == from_fen(fifty_fen.format(halfmove=98)).key}
    repeat_board = chess.Board()
    for move in ["g1f3", "g8f6", "f3g1", "f6g8"]:
        repeat_board.push_uci(move)
    original_key = from_fen(chess.STARTING_FEN).key
    repeat_record = {"fen": repeat_board.fen(),
                     "referee_outcome": str(repeat_board.outcome(claim_draw=True)),
                     "source_isolated_is_repeat": bool(funcs["is_repeat"](original_key, np.array([original_key], dtype=np.uint64), 1))}
    report = {"method": "Unmodified function AST bodies with decorators removed; numpy scalar behavior and original move generation. No compiled engine, search or JIT was run. This establishes local helper behavior, not any game's best move or runtime.",
              "see": rows, "en_passant_repetition_key": ep_record,
              "tt_key_excludes_halfmove": fifty_record, "second_occurrence": repeat_record,
              "late_clock_at_300": {"moves_to_go": moves_to_go(300, 0),
                                     "allocation_20s": allocation(20000, 300, 0)},
              "history_buffer": {"fixed_capacity": 512, "max_search_ply": 96,
                                  "capacity_exceeded_with_pre_root_history": 512}}
    (ROOT / "lab/odin/code_review_repro.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
