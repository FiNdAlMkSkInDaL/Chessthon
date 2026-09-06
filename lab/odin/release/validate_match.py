"""Audit a complete frozen Odin match suite, then compute paired statistics.

python -m lab.odin.release.validate_match --plan plan.json --suite primary \
    --out primary-audit.json primary-a.jsonl primary-b.jsonl

No engine runs. Incomplete evidence always fails. Protocol faults are never
accepted as playing-strength wins. The result distinguishes evidence validity
from the predeclared strict paired-confidence promotion threshold.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import io
import json
import math
from pathlib import Path

import chess
import chess.pgn

from lab.odin.release.plan import digest, lane_plans, validate_plan
from lab.paired_match_stats import analyze_rows

MEMORY = 2*1024**3
THREADS = ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS',
           'NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def numeric(value):
    return type(value) in (int,float) and math.isfinite(value)


def read_log(path):
    rows, errors = [], []
    try:
        lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    except OSError as exc:
        return [], [f'{Path(path).name}: cannot read ({type(exc).__name__})']
    for number,line in enumerate(lines,1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row,dict):
                raise ValueError('Expected object')
            rows.append(row)
        except ValueError:
            errors.append(f'{Path(path).name}: invalid/incomplete JSON line {number}')
    return rows,errors


def validate_metadata(start, plan, suite_name, plan_hash, errors):
    label = 'metadata '+str(start.get('lane'))
    suite = plan['suites'][suite_name]
    for key in ('base_ms','increment_ms','init_budget_s','ply_cap','source_provenance'):
        require(start.get(key)==plan[key],f'{label}: {key} differs from frozen plan',errors)
    for key,expected in [('plan_sha256',plan_hash),('suite',suite_name),
                         ('openings_sha256',suite['openings_sha256']),
                         ('official_referee_unchanged',True),('official_runner_unchanged',True),
                         ('ready_override',False),('runner_shim',None),('service_runtime_limit_s',900)]:
        require(key in start and start[key]==expected,f'{label}: {key} differs/missing',errors)
    require(start.get('thread_env')=={name:'1' for name in THREADS},f'{label}: thread environment differs',errors)
    runtime = start.get('runtime',{})
    require(str(runtime.get('python','')).startswith('3.12.') and
            runtime.get('machine')=='x86_64' and str(runtime.get('platform','')).startswith('Linux-'),
            f'{label}: not Linux x86_64 Python 3.12',errors)
    require(runtime.get('packages')==plan['packages'],f'{label}: package identity differs',errors)
    require(bool(runtime.get('cpu_models')),f'{label}: CPU model missing',errors)
    for role in ('candidate','baseline'):
        snapshot = start.get(role,{})
        require(snapshot.get('sha256')==suite[role+'_sha256'],f'{label}: {role} ZIP identity differs',errors)
        require(snapshot.get('private_snapshot_verified') is True,f'{label}: {role} snapshot unverified',errors)
        entries = snapshot.get('entries',[])
        require(isinstance(entries,list) and bool(entries) and
                sum(e.get('name')=='agent.py' for e in entries)==1,
                f'{label}: {role} manifest lacks exactly one root agent.py',errors)
        names = [entry.get('name') for entry in entries]
        require(len(names)==len(set(names)),f'{label}: {role} duplicate archive member',errors)
        for entry in entries:
            sha = entry.get('sha256','')
            require(len(sha)==64 and all(c in '0123456789abcdef' for c in sha),
                    f'{label}: {role} invalid source digest',errors)
    return suite


def validate_service(timing, cpu, role, expected_moves, base_ms, increment_ms, errors, label):
    require(timing.get('role')==role and timing.get('cpu')==cpu,f'{label}: role/CPU mismatch',errors)
    require(timing.get('envelope_errors')==[] and 'cleanup_error' in timing and timing['cleanup_error'] is None,
            f'{label}: envelope/cleanup missing or failed',errors)
    require(numeric(timing.get('init_s')) and 0<=timing['init_s']<90,f'{label}: init outside 90-second ceiling',errors)
    peak = timing.get('memory_peak_bytes')
    require(type(peak) is int and 0<peak<=MEMORY,f'{label}: missing/over-limit memory peak',errors)
    samples = timing.get('memory_samples',[])
    require(len(samples)==2 and {s.get('phase') for s in samples}=={'after_init','before_stop'},
            f'{label}: expected both resource samples',errors)
    for sample in samples:
        for key,value in [('MemoryMax',str(MEMORY)),('MemorySwapMax','0'),('TasksMax','128'),
                          ('NoNewPrivileges','yes'),('LimitFSIZE','268435456'),
                          ('RestrictAddressFamilies','AF_UNIX'),('ActiveState','active'),
                          ('query_returncode',0),('CPUAffinity',str(cpu))]:
            require(sample.get(key)==value,f'{label}: invalid {key} resource evidence',errors)
        require(not sample.get('query_error') and int(sample.get('MainPID',0))>0,
                f'{label}: invalid service process evidence',errors)
        require(sample.get('CPUQuotaPerSecUSec') in ('1s','1000000us','1000000'),f'{label}: invalid CPU quota',errors)
        require(sample.get('RuntimeMaxUSec') in ('15min','15min 0s','900s','900000000us'),
                f'{label}: missing runtime ceiling',errors)
    moves = timing.get('moves',[])
    require(len(moves)==expected_moves==timing.get('move_count'),f'{label}: move count mismatch',errors)
    for index,move in enumerate(moves):
        require(move.get('ok') is True and move.get('request')==index+1,f'{label}: failed/misnumbered request',errors)
        require(numeric(move.get('elapsed_ms')) and move['elapsed_ms']>=0 and
                type(move.get('time_left_ms')) is int and move['time_left_ms']>=0,
                f'{label}: malformed clock',errors)
        if numeric(move.get('elapsed_ms')) and type(move.get('time_left_ms')) is int:
            require(move['elapsed_ms']<=move['time_left_ms']+1.1,f'{label}: success exceeds clock',errors)
    if moves:
        require(moves[0]['time_left_ms']==base_ms,f'{label}: wrong initial clock',errors)
    residuals = [a['time_left_ms']-a['elapsed_ms']+increment_ms-b['time_left_ms']
                 for a,b in zip(moves,moves[1:])]
    require(min(residuals,default=0)>=-1.1,f'{label}: clock gains unexplained time',errors)
    # Positive residuals include real referee overhead and scheduler delays;
    # retain them diagnostically without inventing an overhead ceiling.
    return residuals


def validate_game(game, start, declared, suite, errors):
    label = str(start['lane'])+' game '+str(game.get('game'))
    for key,value in declared.items():
        require(game.get(key)==value,f'{label}: {key} differs from frozen plan',errors)
    for role in ('candidate','baseline'):
        require(game.get(role+'_sha256')==suite[role+'_sha256'],f'{label}: {role} hash differs',errors)
    require(game.get('candidate_failure') is False and game.get('baseline_failure') is False,
            f'{label}: operational failure or missing marker',errors)
    require(game.get('extraction_errors')=={'white':[],'black':[]},f'{label}: source extraction changed/unverified',errors)
    parsed = chess.pgn.read_game(io.StringIO(game['pgn']))
    require(parsed is not None and not parsed.errors,f'{label}: invalid PGN',errors)
    if parsed is None or parsed.errors:
        return None
    board = chess.Board(declared['fen'])
    require(parsed.board().fen()==board.fen(),f'{label}: PGN starting FEN differs',errors)
    counters = {'white':0,'black':0}
    for node in parsed.mainline():
        colour = 'white' if board.turn else 'black'
        require(board.outcome(claim_draw=True) is None and board.ply()<600,
                f'{label}: play continues after current referee termination',errors)
        request = game[colour+'_timing']['moves'][counters[colour]]
        require(request.get('fen')==board.fen() and request.get('move')==node.move.uci(),
                f'{label}: request FEN/UCI differs from legal replay',errors)
        require(node.move in board.legal_moves,f'{label}: illegal move',errors)
        if node.move not in board.legal_moves:
            return None
        board.push(node.move)
        counters[colour] += 1
    outcome = board.outcome(claim_draw=True)
    if outcome is not None:
        result = 'draw' if outcome.winner is None else 'white' if outcome.winner else 'black'
        termination = outcome.termination.name.lower()
    elif board.ply()>=600:
        result,termination = 'draw','ply_cap'
    else:
        errors.append(f'{label}: game has no current-referee terminal outcome')
        return None
    require(game.get('result')==result and game.get('termination')==termination and
            parsed.headers.get('Termination')==termination and
            parsed.headers.get('Result')=={'white':'1-0','black':'0-1','draw':'1/2-1/2'}[result],
            f'{label}: result/termination differs from legal replay',errors)
    candidate_colour = 'white' if declared['white_role']=='candidate' else 'black'
    points = .5 if result=='draw' else float(result==candidate_colour)
    require(game.get('candidate_colour')==candidate_colour and game.get('candidate_points')==points,
            f'{label}: candidate score/colour mismatch',errors)
    units,residuals = [],[]
    for colour in ('white','black'):
        role = declared[colour+'_role']
        require(game.get(colour+'_sha256')==suite[role+'_sha256'],f'{label}: {colour} source hash differs',errors)
        timing = game[colour+'_timing']
        residuals.extend(validate_service(timing,start['cpu'],role,counters[colour],start['base_ms'],
                                          start['increment_ms'],errors,label+' '+colour))
        units.append(timing.get('unit'))
    return {'plies':len(board.move_stack),'units':units,
            'min_clock_residual_ms':min(residuals,default=0),'max_clock_residual_ms':max(residuals,default=0)}


def apply_criterion(stats,suite):
    """Keep paired uncertainty, but apply the suite's predeclared decision rule."""
    criterion = suite.get('criterion','paired_ci_lower')
    stats['gate']['criterion'] = criterion
    if criterion=='paired_ci_lower':
        return stats
    stats['paired_ci_gate_diagnostic'] = {'verdict':stats['verdict'],'reasons':list(stats['reasons'])}
    reasons = []
    if stats.get('validation_errors'):
        reasons.append(f"{len(stats['validation_errors'])} validation error(s)")
    for key in ('candidate_failures','opponent_failures'):
        count = sum(stats.get(key,{}).values())
        if count:
            reasons.append(f'{count} {key}')
    if stats.get('included_pairs',0)<suite['min_pairs']:
        reasons.append(f"need {suite['min_pairs']} valid pairs, have {stats.get('included_pairs',0)}")
    score = stats.get('score')
    if score is None or score<=suite['threshold']:
        reasons.append(f"final raw score {score!r} is not above threshold {suite['threshold']:.4f}")
    stats['verdict'] = 'PASS' if not reasons else 'FAIL'
    stats['reasons'] = reasons
    return stats


def audit(plan, plan_hash, suite_name, logs, bootstrap_samples=20000):
    errors,games,replays,starts = [],[],[],[]
    try:
        validate_plan(plan)
        suite = plan['suites'][suite_name]
    except (KeyError,TypeError,ValueError) as exc:
        return {'verdict':'FAIL','evidence_valid':False,'failure_reasons':['Invalid plan: '+str(exc)]}
    expected_lanes = {lane['id']:lane for lane in suite['lanes']}
    observed_lanes = []
    for label,rows in logs:
        try:
            ss = [r for r in rows if r.get('type')=='run_start']
            ends = [r for r in rows if r.get('type')=='run_summary']
            gs = [r for r in rows if r.get('type')=='game']
            require(len(ss)==len(ends)==1,f'{label}: missing/duplicate start or summary',errors)
            require(bool(rows) and rows[0].get('type')=='run_start' and rows[-1].get('type')=='run_summary',
                    f'{label}: incomplete or misordered log',errors)
            require(all(r.get('type') in ('run_start','game','run_summary') for r in rows),
                    f'{label}: error or unrecognized row',errors)
            if len(ss)!=1:
                continue
            start = ss[0]
            starts.append(start)
            validate_metadata(start,plan,suite_name,plan_hash,errors)
            lane_id = start['lane']
            observed_lanes.append(lane_id)
            lane = expected_lanes[lane_id]
            declared = [asdict(p) for p in lane_plans(suite,lane_id)]
            require(start.get('cpu')==lane['cpu'],f'{label}: CPU differs from lane plan',errors)
            require(start.get('plans')==declared,f'{label}: game plan differs from frozen plan',errors)
            require(start.get('pairs_planned')==len(declared)//2,f'{label}: pair count differs',errors)
            require([g.get('game') for g in gs]==list(range(1,len(declared)+1)),f'{label}: missing/duplicate/unordered games',errors)
            require(bool(start.get('run_id')) and all(r.get('run_id')==start['run_id'] for r in rows),
                    f'{label}: run identity differs',errors)
            for game in gs:
                before = len(errors)
                try:
                    replay = validate_game(game,start,declared[game['game']-1],suite,errors)
                    if replay and len(errors)==before:
                        replays.append(replay)
                except (KeyError,IndexError,TypeError,ValueError) as exc:
                    errors.append(f'{label}: malformed game {game.get("game")} ({type(exc).__name__})')
            games.extend(gs)
            if len(ends)==1:
                for key,value in [('games_completed',len(declared)),('pairs_completed',len(declared)//2),
                                  ('protocol_failures',0),('planned_games',len(declared))]:
                    require(ends[0].get(key)==value,f'{label}: summary {key} differs',errors)
        except (KeyError,IndexError,TypeError,ValueError) as exc:
            errors.append(f'{label}: malformed run ({type(exc).__name__}: {exc})')
    require(sorted(observed_lanes)==sorted(expected_lanes), 'Missing/duplicate/unexpected suite lanes',errors)
    require(len({s.get('run_id') for s in starts})==len(starts),'Duplicate run identities',errors)
    expected_games = 2*len(suite['openings'])
    require(len(games)==len(replays)==expected_games,f'Expected {expected_games} replay-verified games; got {len(replays)}',errors)
    units = [unit for replay in replays for unit in replay['units']]
    require(len(units)==2*expected_games and len(set(units))==len(units) and None not in units,
            'Every game side must have a distinct fresh agent service',errors)
    if starts:
        for start in starts[1:]:
            for role in ('candidate','baseline'):
                require(start.get(role,{}).get('entries')==starts[0].get(role,{}).get('entries'),
                        f'Lanes disagree on {role} archive contents',errors)
    try:
        stats = analyze_rows(games,source='<frozen-native-'+suite_name+'>',bootstrap_samples=bootstrap_samples,
                             min_pairs=suite['min_pairs'],threshold=suite['threshold'])
        stats = apply_criterion(stats,suite)
    except (KeyError,TypeError,ValueError) as exc:
        stats = {'verdict':'FAIL','reasons':['Malformed scoring evidence: '+type(exc).__name__]}
    reasons = list(dict.fromkeys(errors))
    if stats['verdict']!='PASS':
        reasons += ['Statistical gate: '+reason for reason in stats.get('reasons',[])]
    return {'verdict':'PASS' if not reasons else 'FAIL','evidence_valid':not errors,
            'failure_reasons':reasons,'plan_sha256':plan_hash,'suite':suite_name,
            'candidate_sha256':suite['candidate_sha256'],'baseline_sha256':suite['baseline_sha256'],
            'games_replayed':len(replays),'plies_replayed':sum(r['plies'] for r in replays),
            'statistics':stats,'clock_recurrence_residual_ms':{
                'min':min((r['min_clock_residual_ms'] for r in replays),default=None),
                'max':max((r['max_clock_residual_ms'] for r in replays),default=None)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--suite',required=True)
    parser.add_argument('--out',type=Path)
    parser.add_argument('logs',nargs='+',type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding='utf-8-sig'))
    parsed = [read_log(path) for path in args.logs]
    report = audit(plan,digest(args.plan),args.suite,[(p.name,rows) for p,(rows,_) in zip(args.logs,parsed)])
    parse_errors = [error for _,errors in parsed for error in errors]
    if parse_errors:
        report.update(verdict='FAIL',evidence_valid=False)
        report['failure_reasons'] = parse_errors+report['failure_reasons']
    report['log_sha256'] = {p.name:digest(p) for p in args.logs if p.is_file()}
    rendered = json.dumps(report,indent=2,allow_nan=False)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(rendered,encoding='utf-8',newline='\n')
    print(rendered,end='')
    return 0 if report['verdict']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
