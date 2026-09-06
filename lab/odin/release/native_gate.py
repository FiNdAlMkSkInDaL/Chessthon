"""Cold native exact-ZIP probe and unchanged-official-runner protocol gate.

Run only on Linux x86_64 Python 3.12. Both fresh processes receive the same
one-core/2-GiB/no-swap/thread/no-network-creation envelope as native matches.
--odin-rules additionally verifies absolute-ply cap and long-history searches.
No ZIP is built, no readiness override occurs, and no engine is launched by
--help. A native performance probe is a diagnostic, not an Elo measurement.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import uuid


def dispatch_search(core,pos,moves,hard_ms,soft_ms,history,absolute_ply):
    """Use named arguments for the two audited Python search-root APIs.

    Storm's rules control derives absolute ply from the supplied position FEN;
    Odin additionally accepts it explicitly. Original Storm's historical
    adjudication switch is disabled for generic performance/deadline probes.
    """
    parameters = inspect.signature(core.search_root).parameters
    if 'absolute_ply' in parameters and 'game_zkeys' in parameters:
        return core.search_root(pos,moves,hard_ms,soft_ms,
                                game_zkeys=history,absolute_ply=absolute_ply)
    if 'adjudicate' in parameters and 'game_zkeys' in parameters:
        actual_ply = 2*(int(pos.fullmove)-1)+int(pos.side)
        if actual_ply != absolute_ply:
            raise ValueError('Legacy API derives a different absolute ply from FEN')
        return core.search_root(pos,moves,hard_ms,soft_ms,adjudicate=False,game_zkeys=history)
    raise ValueError('Unknown search_root API; refuse to guess argument ordering')


def worker(args):
    root,source = args.validation_root.resolve(),args.source.resolve()
    sys.path.insert(0,str(root))
    sys.path.insert(0,str(source))
    import chess
    began = time.perf_counter()
    import agent
    import core_nb as core
    cold_s = time.perf_counter()-began
    assert Path(agent.__file__).resolve().is_relative_to(source)
    assert core.NUMBA_READY, 'Original NUMBA_READY is false'
    assert core.root_search_nb.nopython_signatures, 'No warmed native root signature'
    assert cold_s<90, ('competition init ceiling',cold_s)
    assert cold_s<args.cold_target, ('predeclared native cold target',cold_s,args.cold_target)
    from board_nb import from_fen
    from movegen_nb import generate_legal,move_uci
    from lab.perft import POSITIONS
    perft = []
    for name,fen,expected in POSITIONS:
        assert chess.Board(fen).is_valid()
        began = time.perf_counter()
        got = core.perft_pos(from_fen(fen),3)
        seconds = time.perf_counter()-began
        assert got==expected[3], (name,got,expected[3])
        perft.append({'name':name,'depth':3,'nodes':got,'seconds':seconds})
    positions = [POSITIONS[0][1],POSITIONS[1][1],POSITIONS[2][1],
                 '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1']
    probes = []
    for fen in positions:
        board = chess.Board(fen)
        assert board.is_valid() and board.outcome(claim_draw=True) is None
        for budget in (30,100,300):
            pos = from_fen(fen)
            before = (pos.key,core.pack_pos(pos))
            moves = generate_legal(pos)
            began = time.perf_counter()
            choice = dispatch_search(core,pos,moves,float(budget),0.0,[pos.key],board.ply())
            elapsed_ms = 1000*(time.perf_counter()-began)
            assert choice in moves and chess.Move.from_uci(move_uci(choice)) in board.legal_moves
            assert elapsed_ms<budget+200, ('deadline overrun',fen,budget,elapsed_ms)
            import numpy as np
            assert pos.key==before[0] and all(np.array_equal(a,b) for a,b in zip(before[1],core.pack_pos(pos)))
            probes.append({'fen':fen,'hard_ms':budget,'elapsed_ms':elapsed_ms,
                           'move':move_uci(choice),'info':core.last_info()})
    special = []
    if args.odin_rules:
        for fen,expected_mate in [
                ('7k/7p/8/8/8/8/P7/K7 b - - 0 300',False),
                ('8/8/8/8/8/k7/2q5/K7 b - - 0 300',True)]:
            board = chess.Board(fen)
            assert board.is_valid() and board.ply()==599 and board.outcome(claim_draw=True) is None
            pos = from_fen(fen)
            moves = generate_legal(pos)
            choice = dispatch_search(core,pos,moves,250.0,0.0,[pos.key],599)
            score = core.last_info()['score']
            assert score>=31000 if expected_mate else score==0
            board.push_uci(move_uci(choice))
            assert board.is_checkmate() if expected_mate else board.ply()==600
            special.append({'fen':fen,'move':move_uci(choice),'score':score})
        fen = '7k/7p/8/8/8/8/P7/K7 w - - 0 210'
        for length in (500,620,750,900):
            pos = from_fen(fen)
            moves = generate_legal(pos)
            # Synthetic history tests storage bounds, not a claimed legal path.
            history = list(range(1,length))+[pos.key]
            began = time.perf_counter()
            choice = dispatch_search(core,pos,moves,100.0,0.0,history,418)
            elapsed_ms = 1000*(time.perf_counter()-began)
            assert choice in moves and elapsed_ms<300
            special.append({'history_length':length,'move':move_uci(choice),'elapsed_ms':elapsed_ms})
    result = {'verdict':'PASS','source':str(source),'cold_agent_import_s':cold_s,
              'search_root_signature':str(inspect.signature(core.search_root)),
              'warmup_s':core.WARMUP_S,'original_numba_ready':bool(core.NUMBA_READY),
              'nopython_root_signatures':[str(s) for s in core.root_search_nb.nopython_signatures],
              'perft':perft,'deadline_probes':probes,'current_rules_and_history_probes':special}
    args.output.write_text(json.dumps(result,indent=2,default=str)+'\n',encoding='utf-8')
    # The controller samples the live cgroup before asking the worker to stop.
    print(json.dumps({'ready':True}),flush=True)
    sys.stdin.readline()


def run(args):
    from lab.odin.release import linux_match as match
    if sys.platform!='linux' or sys.version_info[:2]!=(3,12) or platform.machine()!='x86_64':
        raise SystemExit('Native gate requires Linux x86_64 Python 3.12')
    if args.cpu not in os.sched_getaffinity(0):
        raise SystemExit('Unavailable CPU')
    if args.output.exists():
        raise SystemExit('Refusing to replace existing gate evidence')
    owner = Path(tempfile.mkdtemp(prefix='chesstk-odin-gate-')).resolve()
    agents = []
    keep = False
    report = {'verdict':'FAIL','runtime':match.runtime_identity(),'cpu':args.cpu,
              'service_runtime_limit_s':900,
              'cold_target_s':args.cold_target,'odin_rules_required':args.odin_rules,
              'limitations':['Signer CPU differs from competition CPU.',
                             'Read-only source uses modes, without a read-only root mount.',
                             'Private temp has no aggregate 256 MiB filesystem quota.']}
    try:
        snapshot = match.snapshot_archive(args.archive,'candidate',owner/'snapshots')
        snapshot.snapshot_path.chmod(0o444)
        report['archive'] = dict(match.snapshot_json(snapshot),entries=snapshot.entries)
        from lab.odin.release.plan import source_provenance,digest
        report['source_provenance'] = source_provenance(args.validation_root,args.harness_root)
        report['gate_provenance'] = {str(p.relative_to(args.validation_root)):digest(p) for p in
                                    (Path(__file__).resolve(),args.validation_root/'lab/perft.py')}
        for phase in ('structural','protocol'):
            stage = owner/phase
            stage.mkdir()
            source,home = stage/'source',stage/'home'
            match.safe_extract(snapshot,source)
            match.make_readonly(source)
            home.mkdir(mode=0o700)
            unit = 'chesstk-odin-gate-'+uuid.uuid4().hex+'-'+phase+'.service'
            bot = match.TimedAgent(source,home,args.cpu,unit,'candidate')
            agents.append(bot)
            if phase=='structural':
                command = match.runner_command(source,home,args.cpu,unit)
                split = command.index('--')
                command = command[:split+1]+['taskset','-c',str(args.cpu),sys.executable,'-B','-u',
                         str(Path(__file__).resolve()),'--worker','--source',str(source),
                         '--validation-root',str(args.validation_root),'--output',str(home/'probe.json'),
                         '--cold-target',str(args.cold_target)]
                if args.odin_rules:
                    command.append('--odin-rules')
                match.Agent.__init__(bot,command)
                bot.start(180.0)
                report['structural'] = json.loads((home/'probe.json').read_text())
            else:
                import chess
                bot.start(90.0)
                assert bot.init_s<args.cold_target, ('official import cold target',bot.init_s)
                moves = []
                for fen,clock in [(chess.STARTING_FEN,100),(chess.STARTING_FEN,450),
                                  (chess.STARTING_FEN,1000),
                                  ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',1000)]:
                    began = time.perf_counter()
                    uci = bot.move(fen,clock)
                    elapsed_ms = 1000*(time.perf_counter()-began)
                    assert chess.Move.from_uci(uci) in chess.Board(fen).legal_moves
                    assert elapsed_ms<clock, ('protocol deadline',clock,elapsed_ms)
                    moves.append({'fen':fen,'time_left_ms':clock,'move':uci,'elapsed_ms':elapsed_ms})
                report['protocol'] = {'cold_agent_import_s':bot.init_s,'moves':moves}
            bot.stop()
            report[phase+'_service'] = bot.report()
            assert bot.cleanup_error is None and not bot.envelope_errors
            errors = match.extraction_problems(snapshot,source)
            match.verify_snapshot(snapshot)
            assert not errors,errors
            report[phase+'_extraction_errors'] = errors
        report['verdict'] = 'PASS'
    except BaseException as exc:
        report['error'] = type(exc).__name__+': '+str(exc)
        raise
    finally:
        for bot in agents:
            try:
                bot.stop()
            except BaseException as exc:
                keep = True
                report.setdefault('cleanup_errors',[]).append(str(exc))
            keep = keep or bool(bot.cleanup_error)
        if keep:
            report['preserved_temporary_tree'] = str(owner)
            report['verdict'] = 'FAIL'
        else:
            match.cleanup_owned_tree(owner,owner.parent)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')
        print(json.dumps({'verdict':report['verdict'],'output':str(args.output)}),flush=True)


def main():
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation-root',type=Path,default=root)
    parser.add_argument('--harness-root',type=Path,default=root/'lab/odin/official-harness-91f70e54')
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--cpu',type=int,default=0)
    parser.add_argument('--cold-target',type=float,default=60.0)
    parser.add_argument('--odin-rules',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--source',type=Path,help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.validation_root = args.validation_root.resolve()
    args.harness_root = args.harness_root.resolve()
    if args.worker:
        worker(args)
    else:
        if args.archive is None:
            parser.error('--archive is required')
        run(args)


if __name__=='__main__':
    main()
