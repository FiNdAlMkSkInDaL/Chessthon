"""Bounded offline reference review of completed development games only."""
import argparse
import ctypes
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import time

import chess
import chess.engine
import chess.pgn

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.odin.reference_review import score_info


def analyse(engine,board,nodes,root_moves=None):
    outcome=board.outcome(claim_draw=True)
    if outcome:
        return {'terminal':outcome.termination.name,
                'white_cp':0 if outcome.winner is None else (32000 if outcome.winner else -32000),
                'white_mate':None,'pv_uci':[],'pv_san':[],'depth':None,'nodes':0}
    info=engine.analyse(board,chess.engine.Limit(nodes=nodes),game=object(),root_moves=root_moves)
    result=score_info(board,info)
    result.update(lowerbound=bool(info.get('lowerbound',False)),upperbound=bool(info.get('upperbound',False)))
    return result


def pin_cpu4(pid,cpu=4):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    kernel.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x600,0,pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.SetProcessAffinityMask(handle,1<<cpu):
            raise ctypes.WinError(ctypes.get_last_error())
        actual,system=ctypes.c_size_t(),ctypes.c_size_t()
        if not kernel.GetProcessAffinityMask(handle,ctypes.byref(actual),ctypes.byref(system)):
            raise ctypes.WinError(ctypes.get_last_error())
        assert actual.value==1<<cpu
    finally:
        kernel.CloseHandle(handle)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--log',type=Path,required=True)
    parser.add_argument('--game',type=int,default=1)
    parser.add_argument('--cpu',type=int,default=4)
    parser.add_argument('--nodes',type=int,default=100000)
    parser.add_argument('--plies',help='Comma-separated relative plies; also search actual root move separately')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    import os
    pin_cpu4(os.getpid(),args.cpu)
    raw=args.log.read_bytes()
    rows=[json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
    start=next(r for r in rows if r.get('type')=='run_start')
    row=next(r for r in rows if r.get('type')=='game' and r['game']==args.game)
    game=chess.pgn.read_game(io.StringIO(row['pgn']))
    assert game is not None and not game.errors
    selected=None if args.plies is None else {int(s) for s in args.plies.split(',')}
    exe=Path('stockfish')
    began=time.perf_counter()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with chess.engine.SimpleEngine.popen_uci(str(exe)) as engine,args.out.open('x',encoding='utf-8') as out:
        pin_cpu4(engine.transport.get_pid(),args.cpu)
        engine.configure({'Threads':1,'Hash':128,'UCI_ShowWDL':True})
        def emit(value):
            out.write(json.dumps(value,allow_nan=False)+'\n')
            out.flush()
        emit({'type':'metadata','utc':datetime.now(timezone.utc).isoformat(),'engine':engine.id,
              'engine_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
              'cpu':args.cpu,'threads':1,'hash_mb':128,'source_log_sha256':hashlib.sha256(raw).hexdigest(),
              'source_game_sha256':hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest(),
              'candidate_sha256':row['candidate_sha256'],'baseline_sha256':row['baseline_sha256'],
              'base_ms':start['base_ms'],'increment_ms':start['increment_ms'],
              'game':args.game,'candidate_colour':row['candidate_colour'],'nodes_per_search':args.nodes,
              'selected_relative_plies':sorted(selected) if selected is not None else None,
              'note':'Development selection data only; finite-node offline reference, not exact truth or shipped lookup data. Full legal PGN history and fresh engine game state at each analysis.'})
        board=game.board()
        moves=list(game.mainline_moves())
        timing={colour:iter(row[colour+'_timing']['moves']) for colour in ('white','black')}
        telemetry={colour:{r['game_ply']:r for r in row[colour+'_timing'].get('search_telemetry',[])} for colour in ('white','black')}
        count=0
        for ply in range(len(moves)+1):
            move=moves[ply] if ply<len(moves) else None
            colour='white' if board.turn else 'black'
            tm=next(timing[colour]) if move else None
            if tm:
                assert tm['fen']==board.fen() and tm['move']==move.uci()
            if selected is None or ply in selected:
                rec={'type':'position','ply':ply,'absolute_ply':board.ply(),'fen':board.fen(),
                     'move_number':board.fullmove_number,'turn':colour,'candidate_turn':colour==row['candidate_colour'],
                     'played_uci':move.uci() if move else None,'played_san':board.san(move) if move else None,
                     'timing':tm,'telemetry':telemetry[colour].get(board.ply())}
                rec.update(analyse(engine,board,args.nodes))
                if selected is not None and move and not rec.get('terminal'):
                    rec['played_root']=analyse(engine,board,args.nodes,[move])
                emit(rec)
                count+=1
            if move:
                assert move in board.legal_moves
                board.push(move)
        emit({'type':'summary','positions':count,'seconds':time.perf_counter()-began})
    print(json.dumps({'positions':count,'seconds':time.perf_counter()-began,'output':str(args.out)}),flush=True)


if __name__=='__main__':
    main()
