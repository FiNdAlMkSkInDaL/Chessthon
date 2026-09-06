"""Reproduce clock/material forensics from day-one platform PGNs and logs.

Run with the existing ChessTK Python 3.12 environment. No engine, external
evaluation, network, or new dependencies are used. Material changes are
diagnostic triggers, never centipawn-loss or best-move labels.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics

import chess
import chess.pgn

ROOT = Path(__file__).resolve().parents[2]
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
PHASE = {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}
# Human-readable case studies in the accompanying report. These are triggers
# for comparing root traces, not adjudications of whether the game move errs.
CASE_STUDIES = {
    2: {20: 'kingside pawn push before opposing knight invasion',
        23: 'rook/knight coordination as c3 comes under attack',
        30: 'defence before Qf4 and Nxf2 sequence',
        32: 'decision before opponent tactical pawn capture',
        37: 'exposed king and rook/queen defensive coordination',
        38: 'queen-for-rook exchange in the recorded continuation'},
    4: {10: 'preparation before Bxb7 exchange sequence',
        11: 'defence after Bxb7',
        28: 'queenside passed-pawn blockade',
        53: 'rook placement before connected passed-pawn conversion',
        54: 'choice of blockade square before a7'},
    6: {23: 'rook/minor-piece endgame with active enemy centre',
        34: 'king activity before enemy king infiltration',
        39: 'rook endgame before pawn and rook exchanges',
        50: 'decision before rook trade to pawn ending',
        51: 'in-check rook trade and pawn-ending horizon',
        53: 'material-equal pawn ending with enemy king on f3'},
    9: {17: 'tactical central sequence with enemy development compensation',
        19: 'capture before enemy quiet attacking move Bh4',
        23: 'material edge against active rooks and bishops',
        24: 'defence with rook on second rank',
        29: 'king shelter and bishop invasion',
        30: 'pawn capture before Rg2+'},
    10: {57: 'perpetual-check alternatives with opposing passer on c7',
         61: 'move creates second occurrence before automatic draw'},
    12: {15: 'central capture before tactical simplification',
         18: 'rook defence before forcing queen trade',
         21: 'decision before Nxf2+',
         23: 'pawn capture before Re8 rook invasion',
         30: 'two-rook endgame and king activity',
         51: 'rook activity versus connected passer preparation',
         64: 'defence before g4'},
    15: {14: 'exchange sacrifice sequence beginning Nxd5',
         16: 'king attack and knight sacrifice on g2',
         37: 'second occurrence in materially inferior position'},
}


def material(board, colour):
    return sum(value * (len(board.pieces(piece, colour)) - len(board.pieces(piece, not colour)))
               for piece, value in VALUES.items())


def phase(board):
    return min(24, sum(value * len(board.pieces(piece, colour))
                       for piece, value in PHASE.items() for colour in chess.COLORS))


def mean(values):
    return round(statistics.mean(values), 3) if values else None


def field(log, label):
    match = re.search(r'^  ' + re.escape(label) + r'\s{2,}(.+)$', log, re.M)
    if not match:
        raise ValueError(f'Missing log field {label}')
    return match.group(1).strip()


def read_game(path):
    log_path = path.with_suffix('.log')
    log = log_path.read_text(encoding='utf-8-sig')
    with path.open(encoding='utf-8-sig') as stream:
        game = chess.pgn.read_game(stream)
    assert game is not None and not game.errors, (path, game.errors)
    colour = field(log, 'Colour') == 'White'
    round_number = int(re.search(r'round-(\d+)', path.name).group(1))
    board = game.board()
    assert board.fen() == field(log, 'Start FEN'), path
    clocks = {chess.WHITE: 120.0, chess.BLACK: 120.0}
    counts = collections.Counter()
    rows = []
    moves = []
    log_moves = re.findall(r'^\s+(\d+)\s+(\S+)\s+([\d.]+) s\s+([\d.]+) s$', log, re.M)
    own_log_rows = []
    for node in game.mainline():
        turn = board.turn
        counts[turn] += 1
        clock = node.clock()
        assert clock is not None, (path, node.ply())
        elapsed = clocks[turn] + .5 - clock
        assert elapsed >= -0.001, (path, elapsed)
        legal = list(board.legal_moves)
        assert node.move in legal, (path, node.move)
        san = board.san(node.move)
        row = {
            'id': f'r{round_number:02d}-p{len(rows):03d}', 'round': round_number,
            'opponent': field(log, 'Opponent'), 'our_colour': 'white' if colour else 'black',
            'ours': turn == colour, 'own_side_move_number': counts[turn],
            'game_ply': len(rows), 'fen': board.fen(),
            'start_fen': game.headers['FEN'], 'history_uci': list(moves),
            'move_uci': node.move.uci(), 'move_san': san,
            'clock_before_s': round(clocks[turn], 3), 'elapsed_s': round(elapsed, 3),
            'clock_after_s': round(clock, 3), 'legal_moves': len(legal),
            'in_check': board.is_check(), 'capture': board.is_capture(node.move),
            'zeroing': board.is_zeroing(node.move), 'phase': phase(board),
            'material_ours': material(board, colour),
            'claimable_draw_before': board.can_claim_draw(),
            'is_second_occurrence': board.is_repetition(2),
        }
        if turn == colour:
            own_log_rows.append((counts[turn], san, elapsed, clock))
        clocks[turn] = clock
        board.push(node.move)
        row['material_ours_after'] = material(board, colour)
        row['claimable_draw_after'] = board.can_claim_draw()
        row['second_occurrence_after'] = board.is_repetition(2)
        rows.append(row)
        moves.append(node.move.uci())
    assert len(own_log_rows) == len(log_moves) == int(field(log, 'Moves')), path
    for observed, logged in zip(own_log_rows, log_moves):
        number, san, elapsed, clock = observed
        assert number == int(logged[0]) and san == logged[1], (path, observed, logged)
        assert abs(elapsed - float(logged[2])) <= .1001, (path, observed, logged)
        assert abs(clock - float(logged[3])) <= .051, (path, observed, logged)
    ours = [row for row in rows if row['ours']]
    theirs = [row for row in rows if not row['ours']]
    result = game.headers['Result']
    outcome = 'draw' if result == '1/2-1/2' else 'win' if (result == '1-0') == colour else 'loss'
    end = board.outcome(claim_draw=True)
    # Checkmate/draw claims must agree with the actual legal replay.
    assert end is not None or len(rows) == 300, path
    assert end is None or end.result() == result, (path, end, result)
    for index, row in enumerate(ours[:-1]):
        row['material_delta_to_next_turn'] = ours[index+1]['material_ours'] - row['material_ours']
    bins = [(1, 10), (11, 25), (26, 40), (41, 60), (61, 150)]
    info = {
        'round': round_number, 'opponent': field(log, 'Opponent'),
        'our_colour': 'white' if colour else 'black', 'outcome': outcome,
        'termination': game.headers.get('Termination'), 'game_plies': len(rows),
        'our_moves': len(ours), 'opponent_moves': len(theirs),
        'remaining_s': clocks[colour], 'opponent_remaining_s': clocks[not colour],
        'elapsed_s': round(sum(row['elapsed_s'] for row in ours), 3),
        'opponent_elapsed_s': round(sum(row['elapsed_s'] for row in theirs), 3),
        'mean_move_s': mean([row['elapsed_s'] for row in ours]),
        'max_move_s': max(row['elapsed_s'] for row in ours),
        'our_first20_s': round(sum(row['elapsed_s'] for row in ours[:20]), 3),
        'opponent_first20_s': round(sum(row['elapsed_s'] for row in theirs[:20]), 3),
        'our_clock_bins_s': {f'{lo}-{hi}': mean([r['elapsed_s'] for r in ours if lo <= r['own_side_move_number'] <= hi]) for lo, hi in bins},
        'opponent_clock_bins_s': {f'{lo}-{hi}': mean([r['elapsed_s'] for r in theirs if lo <= r['own_side_move_number'] <= hi]) for lo, hi in bins},
        'final_material_ours': material(board, colour),
        'initial_material_ours': material(game.board(), colour),
        'largest_material_ours': max(r['material_ours'] for r in rows),
        'lowest_material_ours': min(r['material_ours'] for r in rows),
        'final_fen': board.fen(),
        'final_claimable_threefold': board.can_claim_threefold_repetition(),
        'final_claimable_fifty': board.can_claim_fifty_moves(),
        'final_halfmove_clock': board.halfmove_clock,
        'final_threefold_on_board': board.is_repetition(3),
        'init_ready': field(log, 'Ready in'),
        'init_budget': field(log, 'Budget'),
        'match_id': field(log, 'Match ID'),
        'source_pgn': str(path.relative_to(ROOT)).replace('\\', '/'),
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_log_sha256': hashlib.sha256(log_path.read_bytes()).hexdigest(),
        'opening': field(log, 'Opening'),
    }
    return info, rows


def select_diagnostics(info, rows):
    ours = [row for row in rows if row['ours']]
    selected = {}

    def keep(row, reason):
        if row['id'] not in selected:
            selected[row['id']] = dict(row, diagnostic_reasons=[], best_move_uci=None, label_status='unlabelled diagnostic; actual move is not a target')
        selected[row['id']]['diagnostic_reasons'].append(reason)

    keep(ours[0], 'curated starting-position response')
    keep(max(ours, key=lambda r: r['elapsed_s']), 'largest observed time investment')
    for row in ours:
        case = CASE_STUDIES.get(info['round'], {}).get(int(row['fen'].split()[-1]))
        if case:
            keep(row, case)
    # Position *before* the net material decline over our move and reply.
    drops = sorted((r for r in ours if r.get('material_delta_to_next_turn', 0) < 0),
                   key=lambda r: r['material_delta_to_next_turn'])[:2]
    for row in drops:
        keep(row, f"material changes by {row['material_delta_to_next_turn']} before next own turn; may be correct sacrifice")
        index = ours.index(row)
        if index:
            keep(ours[index-1], 'one own turn before selected material transition')
    for threshold in (12, 6):
        candidates = [row for row in ours if row['phase'] <= threshold]
        if candidates:
            keep(candidates[0], f'first own position with PeSTO material phase <= {threshold}/24')
    if info['outcome'] != 'win':
        for row in ours[-5:]:
            keep(row, 'final five own decisions of non-win; preserve full history')
    if info['termination'] == 'threefold_repetition':
        for row in ours:
            if row['second_occurrence_after']:
                keep(row, 'played move creates a second occurrence (not necessarily an error)')
    return list(selected.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'Chess_results_day1')
    parser.add_argument('--output', type=Path, default=ROOT/'lab/storm')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    games, rows, corpus = [], [], []
    for path in sorted(args.source.glob('*.pgn'), key=lambda p: int(re.search(r'round-(\d+)', p.name).group(1))):
        info, moves = read_game(path)
        games.append(info)
        rows.extend(moves)
        corpus.extend(select_diagnostics(info, moves))
    assert len(games) == 15 and sorted(g['round'] for g in games) == list(range(1,16))
    summary = {
        'method': 'Exact PGN clock replay; elapsed = previous own clock + .5 - new own clock. Material uses P1 N3 B3 R5 Q9. No engine evaluations.',
        'results': dict(collections.Counter(game['outcome'] for game in games)),
        'mean_remaining_s': mean([game['remaining_s'] for game in games]),
        'median_remaining_s': statistics.median(game['remaining_s'] for game in games),
        'remaining_by_outcome_s': {kind: mean([g['remaining_s'] for g in games if g['outcome'] == kind]) for kind in ('win','draw','loss')},
        'own_move_count': sum(g['our_moves'] for g in games),
        'unique_start_fens': len(set(r['start_fen'] for r in rows)),
        'first20_own_elapsed_mean_s': mean([g['our_first20_s'] for g in games]),
        'first20_own_elapsed_sd_s': round(statistics.pstdev(g['our_first20_s'] for g in games),3),
        'forced_own_moves': sum(r['ours'] and r['legal_moves'] == 1 for r in rows),
        'forced_own_elapsed_s': round(sum(r['elapsed_s'] for r in rows if r['ours'] and r['legal_moves'] == 1),3),
        'games': games,
    }
    (args.output/'day1_summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    for name, records in [('day1_moves.jsonl', rows), ('day1_diagnostics.jsonl', corpus)]:
        (args.output/name).write_text(''.join(json.dumps(record)+'\n' for record in records), encoding='utf-8')
    (args.output/'day1_diagnostics.fen').write_text(''.join(row['fen']+'\n' for row in corpus), encoding='utf-8')
    columns = ['round','opponent','our_colour','outcome','termination','our_moves','remaining_s','opponent_remaining_s','elapsed_s','our_first20_s','opponent_first20_s','final_material_ours']
    with (args.output/'day1_games.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(games)
    print(json.dumps({k:v for k,v in summary.items() if k != 'games'}, indent=2))
    print(f'Validated {len(rows)} legal plies and all {summary["own_move_count"]} logged own moves; {len(corpus)} diagnostic roots.')
    for game in games:
        print(f"R{game['round']:2} {game['opponent']:16} {game['outcome']:4} {game['termination']:24} moves={game['our_moves']:3} left={game['remaining_s']:7.3f} otherleft={game['opponent_remaining_s']:7.3f} first20={game['our_first20_s']:6.2f}/{game['opponent_first20_s']:6.2f} material={game['final_material_ours']:+3}")


if __name__ == '__main__':
    main()
