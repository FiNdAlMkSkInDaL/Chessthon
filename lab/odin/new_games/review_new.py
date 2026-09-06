"""Review newly supplied site rounds; independent diagnostics, never fitting data."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from lab.odin.development_review.review import pin_cpu4
from lab.odin.reference_review import score_info
import chess
import chess.engine
import chess.pgn


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(engine,board,nodes,root_moves=None):
    outcome=board.outcome(claim_draw=True)
    if outcome:
        return {'white_cp':0 if outcome.winner is None else (32000 if outcome.winner else -32000),
                'terminal':outcome.termination.name,'exact_iteration':True,'nodes':0,'pv_uci':[]}
    engine.configure({'Clear Hash':None})
    last=None;total=0
    with engine.analysis(board,chess.engine.Limit(nodes=nodes),game=object(),root_moves=root_moves) as stream:
        for item in stream:
            total=max(total,item.get('nodes',0))
            if 'score' in item and not item.get('lowerbound') and not item.get('upperbound'):
                last=dict(item)
    assert last is not None
    # A short mate or immediate draw can hit maximum depth before the node cap.
    assert total>=nodes or last['score'].is_mate() or last.get('depth',0)>=245, (total,last)
    return dict(score_info(board,last),exact_iteration=True,total_nodes=total,requested_node_cap=nodes,
                early_natural_completion=total<nodes,
                caveat='Last completed exact alpha-beta iteration, finite reference search; not game-theoretic truth.')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--round',type=int,required=True)
    ap.add_argument('--cpu',type=int,required=True)
    ap.add_argument('--nodes',type=int,default=100000)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--directory',type=Path,default=ROOT/'chess_results_day2')
    ap.add_argument('--output-directory',type=Path,default=HERE)
    args=ap.parse_args()
    import os
    pin_cpu4(os.getpid(),args.cpu)
    files=list(args.directory.resolve().glob(f'aichessathon-round-{args.round}-*.pgn'))
    assert len(files)==1
    path=files[0]
    with path.open(encoding='utf-8-sig') as f:game=chess.pgn.read_game(f)
    assert game and not game.errors
    color=chess.WHITE if game.headers['White']=='Finlay Phillips' else chess.BLACK
    assert game.headers['White' if color else 'Black']=='Finlay Phillips'
    executable=Path('C:/Users/finla/AppData/Local/ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe')
    args.output_directory.mkdir(parents=True,exist_ok=True)
    outpath=args.output_directory/f'round-{args.round}-screen.jsonl'
    existing=[json.loads(s) for s in outpath.read_text(encoding='utf-8').splitlines()] if args.resume else []
    if args.resume:
        assert existing[0]['source_sha256']==sha(path)
        assert not any(r.get('type')=='summary' for r in existing)
    else:
        assert not outpath.exists()
    completed={r['ply']:r for r in existing if r.get('type')=='position'}
    board=game.board();history=[];clocks={chess.WHITE:120000.,chess.BLACK:120000.}
    nodes=list(game.mainline());began=time.perf_counter()
    holdout={" ".join(chess.Board(f).fen(en_passant='legal').split()[:4]) for f in (ROOT/'lab/odin/release_openings/holdout.fen').read_text().splitlines() if f.strip() and not f.startswith('#')}
    overlap=[]
    with chess.engine.SimpleEngine.popen_uci(str(executable)) as engine,outpath.open('a' if args.resume else 'x',encoding='utf-8') as out:
        engine.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
        def emit(row):out.write(json.dumps(row,allow_nan=False)+'\n');out.flush()
        emit({'type':'resume_metadata' if args.resume else 'metadata','round':args.round,'source':str(path.relative_to(ROOT)),'source_sha256':sha(path),
              'headers':dict(game.headers),'engine':engine.id,'engine_sha256':sha(executable),'cpu':args.cpu,
              'nodes_per_reference':args.nodes,'script_sha256':sha(Path(__file__)),'started_utc':datetime.now(timezone.utc).isoformat(),
              'scope':'New site diagnostics only. Candidate coefficients already fixed before receiving these games. Never pool with final holdout.'})
        for ply in range(len(nodes)+1):
            node=nodes[ply] if ply<len(nodes) else None
            move=node.move if node else None
            assert board.is_valid()
            key=' '.join(board.fen(en_passant='legal').split()[:4])
            if key in holdout:overlap.append(ply)
            row={'type':'position','round':args.round,'ply':ply,'absolute_ply':board.ply(),'fen':board.fen(),
                 'start_fen':game.board().fen(),'history_uci':history.copy(),'storm_turn':board.turn==color,
                 'storm_colour':'white' if color else 'black','played_uci':move.uci() if move else None,
                 'played_san':board.san(move) if move else None,'time_left_ms':int(clocks[board.turn]),
                 'clock_after_ms':round(node.clock()*1000) if node and node.clock() is not None else None,
                 'holdout_position_overlap':key in holdout}
            if ply in completed:
                assert completed[ply]['fen']==row['fen'] and completed[ply]['history_uci']==history
            else:
                row.update(reference(engine,board,args.nodes))
                emit(row)
            if node:
                assert move in board.legal_moves
                if node.clock() is not None:clocks[board.turn]=node.clock()*1000
                board.push(move);history.append(move.uci())
        emit({'type':'summary','positions':len(nodes)+1,'holdout_exact_position_overlap_plies':overlap,
              'elapsed_s':time.perf_counter()-began})
    print(json.dumps({'round':args.round,'positions':len(nodes)+1,'holdout_overlap':overlap,'seconds':time.perf_counter()-began}),flush=True)


if __name__=='__main__':main()
