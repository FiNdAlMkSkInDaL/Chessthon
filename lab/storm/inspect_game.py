"""Replay one completed native game and export clocks/material/own telemetry.

No engine search or evaluation runs. Telemetry is a recorded engine estimate.
python -m lab.storm.inspect_game LOG --game 12 --out-prefix lab/storm/r2-loss-165
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import chess
import chess.pgn

from lab.storm.validate_holdout import validate_game


def inspect(log, game_number, prefix):
    lines = [line for line in log.read_bytes().splitlines() if line.strip()]
    records = [(line, json.loads(line)) for line in lines]
    start = next(row for _, row in records if row.get('type') == 'run_start')
    matching = [(line, row) for line, row in records
                if row.get('type') == 'game' and row.get('game') == game_number]
    if len(matching) != 1:
        raise ValueError('Expected exactly one matching completed game')
    raw, game = matching[0]
    plan = next(p for p in start['plans'] if p['game'] == game_number)
    errors = []
    replay = validate_game(game, start, plan, errors)
    if errors or not replay:
        raise ValueError('Game integrity failed: ' + '; '.join(errors))
    board = chess.Board(game['fen'])
    parsed = chess.pgn.read_game(io.StringIO(game['pgn']))
    counts = {'white': 0, 'black': 0}
    telemetry = {colour: {t['game_ply']: t for t in game[colour+'_timing']['s4_telemetry']}
                 for colour in counts}
    trace = []
    for move in parsed.mainline_moves():
        colour = 'white' if board.turn else 'black'
        request = game[colour+'_timing']['moves'][counts[colour]]
        entry = {'ply': len(board.move_stack)+1, 'fullmove': board.fullmove_number,
                 'colour': colour, 'san': board.san(move), 'uci': move.uci(),
                 'fen_before': board.fen(), 'legal_move_count': board.legal_moves.count(),
                 'in_check': board.is_check(), 'request': counts[colour]+1,
                 'time_left_ms': request['time_left_ms'], 'elapsed_ms': request['elapsed_ms'],
                 'estimated_after_ms': request['time_left_ms']-request['elapsed_ms']+start['increment_ms'],
                 'telemetry': telemetry[colour].get(2*counts[colour])}
        board.push(move)
        entry['fen_after'] = board.fen()
        entry['material_after'] = {
            side: {'points': sum(value*len(board.pieces(piece, side=='white'))
                                 for piece,value in ((1,1),(2,3),(3,3),(4,5),(5,9))),
                   'pawns': [chess.square_name(square) for square in board.pieces(chess.PAWN, side=='white')],
                   'king': chess.square_name(board.king(side=='white'))}
            for side in counts}
        trace.append(entry)
        counts[colour] += 1
    sides = {}
    for colour in counts:
        timing = game[colour+'_timing']
        moves = timing['moves']
        sides[colour] = {
            'role': timing['role'], 'move_count': len(moves), 'init_s': timing['init_s'],
            'memory_peak_bytes': timing['memory_peak_bytes'], 'first20_spent_ms': sum(m['elapsed_ms'] for m in moves[:20]),
            'total_spent_ms': sum(m['elapsed_ms'] for m in moves),
            'estimated_final_clock_ms': moves[-1]['time_left_ms']-moves[-1]['elapsed_ms']+start['increment_ms'],
            'telemetry_records': len(timing['s4_telemetry'])}
    summary = {
        'source_log': log.name, 'run_id': start['run_id'], 'game': game_number,
        'pair': game['pair'], 'opening_index': game['opening_index'],
        'source_game_line_sha256': hashlib.sha256(raw).hexdigest(),
        'source_game_line_hash_definition': 'Exact source JSON line bytes, excluding line ending',
        'pgn_sha256': hashlib.sha256(game['pgn'].encode('utf-8')).hexdigest(),
        'candidate_sha256': game['candidate_sha256'], 'baseline_sha256': game['baseline_sha256'],
        'result': game['result'], 'termination': game['termination'], 'plies': len(trace),
        'validation_errors': errors, 'sides': sides,
        'telemetry_mapping': 'p = 2 * (own request number - 1), from each agent first served FEN; missing telemetry remains null',
        'clock_note': 'Final reserves estimated from integer incoming clock minus wrapper elapsed plus increment',
        'trace': trace}
    prefix.parent.mkdir(parents=True, exist_ok=True)
    Path(str(prefix)+'.game.json').write_bytes(raw+b'\n')
    Path(str(prefix)+'.pgn').write_text(game['pgn']+'\n', encoding='utf-8')
    Path(str(prefix)+'.analysis.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    return {key: value for key,value in summary.items() if key != 'trace'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--game', required=True, type=int)
    parser.add_argument('--out-prefix', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.log, args.game, args.out_prefix), indent=2))


if __name__ == '__main__':
    main()
