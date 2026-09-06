"""Audit the two predeclared native Storm-r2/v3 holdout logs, then score them.

python -m lab.storm.validate_holdout lane-a.jsonl lane-b.jsonl --out audit.json

This reads evidence only. Incomplete logs FAIL; the short-clock screen and
supplementary site checks must not be supplied. No engine is imported or run.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path

import chess
import chess.pgn

from lab.paired_match_stats import analyze_rows
from lab.storm.linux_match import MEMORY_LIMIT_BYTES, THREAD_ENV, envelope_problems

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_SHA = '15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c'
BASELINE_SHA = '3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408'
HASHES = {'candidate': CANDIDATE_SHA, 'baseline': BASELINE_SHA}
SOURCE_FILES = (
    'harness/referee.py', 'harness/rules.py', 'harness/runner.py', 'harness/sandbox.py',
    'lab/storm/linux_match.py', 'lab/laptop_match.py', 'lab/laptop_runner.py',
    'lab/release_audit.py', 'lab/paired_match_stats.py',
)
PACKAGES = {'chess': '1.11.2', 'numpy': '2.5.2', 'numba': '0.67.0', 'llvmlite': '0.49.0'}


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def read_log(path):
    rows, errors = [], []
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError as exc:
        return [], [f'{path.name}: cannot read log ({type(exc).__name__})']
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('expected object')
            rows.append(row)
        except (ValueError, json.JSONDecodeError):
            errors.append(f'{path.name}: invalid/incomplete JSON at line {number}')
    return rows, errors


def validate_metadata(start, label, source_hashes, openings_hash, errors):
    """Small independently testable guard against mixed runs and time controls."""
    for key, expected in (('base_ms',120000), ('increment_ms',500), ('init_budget_s',90.0),
                          ('ply_cap',300), ('pairs_planned',10), ('official_referee_unchanged',True),
                          ('official_runner_unchanged',True), ('ready_override',False), ('runner_shim',None)):
        require(key in start and start[key] == expected,
                f'{label}: {key} must be {expected!r}', errors)
    require(start.get('openings_sha256') == openings_hash,
            f'{label}: opening-file identity differs from the declared local corpus', errors)
    require(start.get('source_provenance') == source_hashes,
            f'{label}: harness/runner/helper source identities differ from audited workspace', errors)
    require(start.get('thread_env') == {name:'1' for name in THREAD_ENV},
            f'{label}: single-thread environment is missing or changed', errors)
    runtime = start.get('runtime', {})
    require(str(runtime.get('python','')).startswith('3.12.') and
            runtime.get('machine') == 'x86_64' and str(runtime.get('platform','')).startswith('Linux-'),
            f'{label}: runtime is not native Linux x86_64 Python 3.12', errors)
    require(runtime.get('packages') == PACKAGES, f'{label}: competition package versions differ', errors)
    require(bool(runtime.get('cpu_models')), f'{label}: measured CPU model missing', errors)
    require(type(start.get('cpu')) is int and start['cpu'] >= 0, f'{label}: CPU identity missing', errors)
    for role, digest in HASHES.items():
        snapshot = start.get(role, {})
        require(snapshot.get('sha256') == digest, f'{label}: {role} ZIP hash is not the frozen {role}', errors)
        require(snapshot.get('private_snapshot_verified') is True,
                f'{label}: {role} private ZIP snapshot was not verified', errors)
        entries = snapshot.get('entries', [])
        require(isinstance(entries,list) and bool(entries) and
                sum(e.get('name') == 'agent.py' for e in entries) == 1,
                f'{label}: {role} manifest lacks exactly one root agent.py', errors)


def validate_game(game, start, plan, errors):
    """Replay one legal game; return compact counts/clock approximation data."""
    label = f"run {start['run_id']} game {game.get('game')}"
    for key in ('game','pair','opening_index','fen','white_role','black_role','white_cpu','black_cpu'):
        require(game.get(key) == plan.get(key), f'{label}: {key} differs from predeclared plan', errors)
    for role, digest in HASHES.items():
        require(game.get(role+'_sha256') == digest, f'{label}: {role} game hash mismatch', errors)
    require(game.get('candidate_failure') is False and game.get('baseline_failure') is False,
            f'{label}: protocol failure or missing explicit failure markers', errors)
    require(game.get('extraction_errors') == {'white':[], 'black':[]},
            f'{label}: extraction integrity failed or was not recorded', errors)
    parsed = chess.pgn.read_game(io.StringIO(game['pgn']))
    require(parsed is not None and not parsed.errors, f'{label}: PGN parse failed', errors)
    if parsed is None or parsed.errors:
        return {}
    board = chess.Board(plan['fen'])
    require(parsed.board().fen() == board.fen(), f'{label}: PGN initial position mismatch', errors)
    require(parsed.headers.get('Termination') == game.get('termination'),
            f'{label}: PGN termination disagrees with game row', errors)
    counters = {'white':0, 'black':0}
    for node in parsed.mainline():
        colour = 'white' if board.turn else 'black'
        require(board.outcome(claim_draw=True) is None and len(board.move_stack) < 300,
                f'{label}: PGN continues after the referee would stop', errors)
        moves = game[colour+'_timing']['moves']
        index = counters[colour]
        if index >= len(moves):
            errors.append(f'{label}: missing {colour} timing request')
            return {}
        request = moves[index]
        require(request.get('fen') == board.fen() and request.get('move') == node.move.uci(),
                f'{label}: {colour} request {index+1} FEN/UCI disagrees with PGN', errors)
        require(node.move in board.legal_moves, f'{label}: illegal PGN move', errors)
        if node.move not in board.legal_moves:
            return {}
        board.push(node.move)
        counters[colour] += 1
    outcome = board.outcome(claim_draw=True)
    if outcome is not None:
        result = 'draw' if outcome.winner is None else 'white' if outcome.winner else 'black'
        termination = outcome.termination.name.lower()
        header_result = outcome.result()
    elif len(board.move_stack) == 300:
        balance = sum(value*(len(board.pieces(piece,True))-len(board.pieces(piece,False)))
                      for piece,value in ((1,1),(2,3),(3,3),(4,5),(5,9)))
        result = 'white' if balance>0 else 'black' if balance<0 else 'draw'
        termination = 'adjudication'
        header_result = {'white':'1-0','black':'0-1','draw':'1/2-1/2'}[result]
    else:
        errors.append(f'{label}: nonterminal PGN below the 300-ply cap')
        return {}
    require(game.get('result') == result and game.get('termination') == termination and
            parsed.headers.get('Result') == header_result,
            f'{label}: legal replay result/termination mismatch', errors)
    candidate_colour = 'white' if plan['white_role']=='candidate' else 'black'
    points = .5 if result=='draw' else float(result==candidate_colour)
    require(game.get('candidate_colour') == candidate_colour and game.get('candidate_points') == points,
            f'{label}: candidate colour/score mismatch', errors)
    residuals, units = [], []
    for colour in ('white','black'):
        timing = game[colour+'_timing']
        role = plan[colour+'_role']
        require(game.get(colour+'_sha256') == HASHES[role], f'{label}: {colour} identity mismatch', errors)
        require(timing.get('role') == role and timing.get('cpu') == start['cpu'] and
                plan[colour+'_cpu'] == start['cpu'], f'{label}: {colour} role/CPU mismatch', errors)
        require(timing.get('envelope_errors') == [] and 'cleanup_error' in timing and timing['cleanup_error'] is None,
                f'{label}: {colour} envelope/cleanup error or missing evidence', errors)
        require(numeric(timing.get('init_s')) and 0 <= timing['init_s'] < 90,
                f'{label}: {colour} init did not satisfy 90 seconds', errors)
        peak = timing.get('memory_peak_bytes')
        require(type(peak) is int and 0 < peak <= MEMORY_LIMIT_BYTES,
                f'{label}: {colour} memory peak missing or beyond 2 GiB', errors)
        samples = timing.get('memory_samples', [])
        require({s.get('phase') for s in samples} == {'after_init','before_stop'},
                f'{label}: {colour} missing init/stop envelope samples', errors)
        for sample in samples:
            try:
                affinity = [int(cpu) for cpu in sample.get('CPUAffinity','').split()]
            except ValueError:
                affinity = None
            require(sample.get('query_returncode') == 0 and not sample.get('query_error') and
                    sample.get('ActiveState') == 'active' and int(sample.get('MainPID',0)) > 0,
                    f'{label}: {colour} service sample invalid', errors)
            for issue in envelope_problems(sample, start['cpu'], affinity):
                errors.append(f'{label}: {colour} {issue}')
        moves = timing['moves']
        require(len(moves) == counters[colour] == timing.get('move_count'),
                f'{label}: {colour} move count disagrees with PGN', errors)
        for index, move in enumerate(moves):
            require(move.get('ok') is True and move.get('request') == index+1,
                    f'{label}: {colour} failed/misnumbered request', errors)
            require(numeric(move.get('elapsed_ms')) and move['elapsed_ms'] >= 0 and
                    type(move.get('time_left_ms')) is int and move['time_left_ms'] >= 0,
                    f'{label}: {colour} invalid clock record', errors)
            if numeric(move.get('elapsed_ms')) and type(move.get('time_left_ms')) is int:
                require(move['elapsed_ms'] <= move['time_left_ms']+1.1,
                        f'{label}: {colour} successful request exceeds recorded clock', errors)
        if moves:
            require(moves[0]['time_left_ms'] == 120000,
                    f'{label}: {colour} first clock is not 120000 ms', errors)
        side_residuals = [a['time_left_ms']-a['elapsed_ms']+500-b['time_left_ms']
                          for a,b in zip(moves,moves[1:])]
        require(min(side_residuals,default=0) >= -1.1,
                f'{label}: {colour} clock gains unexplained time beyond truncation', errors)
        residuals.extend(side_residuals)
        units.append(timing.get('unit'))
    return {'plies':len(board.move_stack), 'units':units,
            'min_clock_residual_ms':min(residuals,default=0),
            'max_clock_residual_ms':max(residuals,default=0)}


def audit(logs, source_hashes, opening_fens, openings_hash, bootstrap_samples=20000):
    """Accept [(short_label, parsed_rows), ...]; paths are never in the report."""
    errors, starts, all_games, indices, replays, summaries = [], [], [], [], [], []
    require(len(logs) == 2, 'Exactly two native holdout logs are required', errors)
    for label, rows in logs:
        ss = [r for r in rows if r.get('type')=='run_start']
        gs = [r for r in rows if r.get('type')=='game']
        ends = [r for r in rows if r.get('type')=='run_summary']
        require(len(ss)==1, f'{label}: expected one run_start', errors)
        require(len(ends)==1, f'{label}: incomplete run; expected one final run_summary', errors)
        require(len(gs)==20, f'{label}: incomplete run; expected 20 games, found {len(gs)}', errors)
        require(all(r.get('type') in ('run_start','game','run_summary') for r in rows),
                f'{label}: run_error or unexpected/configuration row present', errors)
        if len(ss)!=1:
            continue
        start = ss[0]
        starts.append(start)
        try:
            validate_metadata(start,label,source_hashes,openings_hash,errors)
            run_id = start['run_id']
            require(bool(run_id) and all(r.get('run_id')==run_id for r in rows),
                    f'{label}: inconsistent run identity', errors)
            require(rows[0].get('type')=='run_start' and rows[-1].get('type')=='run_summary',
                    f'{label}: run is incomplete or metadata order is invalid', errors)
            plans = start.get('plans',[])
            require(len(plans)==20 and [p.get('game') for p in plans]==list(range(1,21)),
                    f'{label}: expected all 20 numbered predeclared game plans', errors)
            require([g.get('game') for g in gs]==list(range(1,21)),
                    f'{label}: missing/duplicated/out-of-order game rows', errors)
            by_number = {p['game']:p for p in plans}
            planned_indices = sorted(set(p['opening_index'] for p in plans))
            require(len(planned_indices)==10, f'{label}: expected ten distinct planned opening indices', errors)
            indices.extend(planned_indices)
            for index in planned_indices:
                pair = [p for p in plans if p['opening_index']==index]
                require(index in range(160,180) and len(pair)==2 and
                        {p['white_role'] for p in pair}=={'candidate','baseline'} and
                        all({p['white_role'],p['black_role']}=={'candidate','baseline'} for p in pair),
                        f'{label}: invalid opening/colour pair at index {index}', errors)
                require(all(p['fen']==opening_fens[index] for p in pair),
                        f'{label}: index {index} FEN differs from predeclared corpus', errors)
            for game in gs:
                try:
                    before = len(errors)
                    replay = validate_game(game,start,by_number[game['game']],errors)
                    if replay and len(errors)==before:
                        replays.append(replay)
                except (KeyError, TypeError, ValueError, IndexError) as exc:
                    errors.append(f'{label}: malformed game {game.get("game")} ({type(exc).__name__})')
            if len(ends)==1:
                end = ends[0]
                for key,expected in (('games_completed',20),('pairs_completed',10),('planned_games',20),('protocol_failures',0)):
                    require(end.get(key)==expected, f'{label}: final {key} must equal {expected}', errors)
                summaries.append({key:end.get(key) for key in ('run_id','games_completed','pairs_completed','planned_games','protocol_failures')})
        except (KeyError,TypeError,ValueError,IndexError) as exc:
            errors.append(f'{label}: malformed run metadata ({type(exc).__name__})')
        all_games.extend(gs)
    require(len(starts)==2 and len({s.get('run_id') for s in starts})==2,
            'The logs must contain two distinct runs', errors)
    require(sorted(indices)==list(range(160,180)),
            'Opening coverage must be disjoint and exactly indices 160–179', errors)
    require(len(all_games)==40 and len(replays)==40,
            f'Expected 40 replay-verified games; found {len(all_games)} rows and {len(replays)} verified replays', errors)
    units = [unit for replay in replays for unit in replay['units']]
    require(len(units)==80 and len(set(units))==80 and None not in units,
            'Expected 80 distinct fresh agent service identities', errors)
    if len(starts)==2:
        require(starts[0].get('cpu') != starts[1].get('cpu'),
                'Concurrent lanes must use distinct CPU IDs', errors)
        for key in ('source_provenance','openings_sha256','thread_env'):
            require(starts[0].get(key)==starts[1].get(key), f'Lanes disagree on {key}', errors)
        for key in ('python','platform','machine','packages','cpu_models'):
            require(starts[0].get('runtime',{}).get(key)==starts[1].get('runtime',{}).get(key),
                    f'Lanes disagree on runtime {key}', errors)
        for role in ('candidate','baseline'):
            require(starts[0].get(role,{}).get('entries')==starts[1].get(role,{}).get('entries'),
                    f'Lanes disagree on {role} ZIP manifest', errors)
    try:
        statistics = analyze_rows(all_games, source='<native-holdout>', bootstrap_samples=bootstrap_samples,
                                  min_pairs=20, threshold=.5)
    except (KeyError,TypeError,ValueError) as exc:
        statistics = {'verdict':'FAIL','reasons':['Malformed scoring evidence: '+type(exc).__name__]}
    reasons = list(dict.fromkeys(errors))
    if statistics['verdict']!='PASS':
        reasons += ['Statistical gate: '+reason for reason in statistics.get('reasons',[])]
    return {'verdict':'PASS' if not reasons else 'FAIL', 'evidence_valid':not errors,
            'failure_reasons':reasons, 'candidate_sha256':CANDIDATE_SHA, 'baseline_sha256':BASELINE_SHA,
            'logs':[label for label,_ in logs], 'required_opening_indices':list(range(160,180)),
            'opening_indices_observed':sorted(indices), 'games_replayed':len(replays),
            'plies_replayed':sum(r['plies'] for r in replays), 'run_summaries':summaries,
            'source_provenance':source_hashes, 'openings_sha256':openings_hash,
            'clock_recurrence_residual_ms':{
                'min':min((r['min_clock_residual_ms'] for r in replays),default=None),
                'max':max((r['max_clock_residual_ms'] for r in replays),default=None),
                'note':'Diagnostic only: incoming clocks are integers; wrapper timing excludes a little referee overhead.'},
            'statistics':statistics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs',nargs=2,type=Path)
    parser.add_argument('--out',type=Path)
    args = parser.parse_args()
    source_hashes = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    openings = ROOT/'lab/openings.fen'
    opening_fens = [line.strip() for line in openings.read_text(encoding='utf-8').splitlines()
                    if line.strip() and not line.lstrip().startswith('#')]
    parsed = [read_log(path) for path in args.logs]
    report = audit([(path.name,rows) for path,(rows,_) in zip(args.logs,parsed)], source_hashes,
                   opening_fens, hashlib.sha256(openings.read_bytes()).hexdigest())
    parse_errors = [error for _,errors in parsed for error in errors]
    if parse_errors:
        report['failure_reasons'] = parse_errors+report['failure_reasons']
        report.update(verdict='FAIL',evidence_valid=False)
    rendered = json.dumps(report,indent=2,allow_nan=False)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(rendered,encoding='utf-8')
    print(rendered,end='')
    return 0 if report['verdict']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
