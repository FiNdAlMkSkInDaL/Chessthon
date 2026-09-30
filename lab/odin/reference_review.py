"""Offline, reproducible Stockfish review. Never imported by submission code."""
from __future__ import annotations
import argparse, hashlib, io, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import chess
import chess.engine
import chess.pgn

ROOT = Path(__file__).resolve().parents[2]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def games():
    result=[]
    for p in sorted((ROOT/'chess_results_day2').glob('*.pgn')):
        with p.open(encoding='utf-8-sig') as f: g=chess.pgn.read_game(f)
        assert not g.errors
        result.append((f'site-r{int(g.headers["Round"])}', g, chess.WHITE if g.headers['White']=='Finlay Phillips' else chess.BLACK, str(p.relative_to(ROOT)), sha(p)))
    for lane in ('a','b'):
        p=ROOT/f'lab/storm/holdout-r2-lane-{lane}.jsonl'
        digest=sha(p)
        for line in p.read_text(encoding='utf-8').splitlines():
            r=json.loads(line)
            if r.get('type')!='game': continue
            g=chess.pgn.read_game(io.StringIO(r['pgn']))
            assert not g.errors
            result.append((f'holdout-{lane}-g{r["game"]}-o{r["opening_index"]}', g, r['candidate_colour']=='white',str(p.relative_to(ROOT)),digest))
    return result

def score_info(board, info):
    s=info['score'].white()
    pv=info.get('pv',[])
    b=board.copy(); san=[]
    for m in pv[:16]:
        assert m in b.legal_moves
        san.append(b.san(m)); b.push(m)
    return {'white_cp':s.score(mate_score=32000),'white_mate':s.mate(),
            'depth':info.get('depth'),'seldepth':info.get('seldepth'),
            'nodes':info.get('nodes'),'seconds':info.get('time'),
            'pv_uci':[m.uci() for m in pv[:16]],'pv_san':san,
            'wdl_white':list(info['wdl'].white()) if 'wdl' in info else None}

def analyse(e,b,nodes,root_moves=None):
    outcome=b.outcome(claim_draw=True)
    if outcome:
        return {'terminal':outcome.termination.name,'white_cp':0 if outcome.winner is None else (32000 if outcome.winner else -32000),'white_mate':None,'pv_uci':[],'pv_san':[],'depth':None,'nodes':0}
    info=e.analyse(b,chess.engine.Limit(nodes=nodes),game=object(),root_moves=root_moves)
    return score_info(b,info)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=('screen','deep'),default='screen')
    parser.add_argument('--selection',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--site-nodes',type=int,default=100000)
    parser.add_argument('--holdout-nodes',type=int,default=50000)
    parser.add_argument('--deep-nodes',type=int,default=2000000)
    args=parser.parse_args()
    exe=Path('stockfish')
    corpus=games(); start=time.perf_counter()
    with chess.engine.SimpleEngine.popen_uci(str(exe)) as e, args.out.open('x',encoding='utf-8') as f:
        e.configure({'Threads':1,'Hash':128,'UCI_ShowWDL':True})
        def emit(r): f.write(json.dumps(r,allow_nan=False)+'\n'); f.flush()
        emit({'type':'metadata','started_utc':datetime.now(timezone.utc).isoformat(),'engine':e.id,'exe_sha256':sha(exe),'threads':1,'hash_mb':128,'clear_hash_each_position':True,'mode':args.mode,'site_nodes':args.site_nodes,'holdout_nodes':args.holdout_nodes,'deep_nodes':args.deep_nodes,'script_sha256':sha(Path(__file__)),'note':'Independent finite-budget offline reference, not ground truth or shipped data. Full available PGN history supplied. Exact python-chess claimable outcomes override reference score.'})
        selection=json.loads(args.selection.read_text()) if args.selection else None
        total=0
        for gid,g,colour,source,digest in corpus:
            wanted=None if selection is None else {r['ply']:r for r in selection if r['game_id']==gid}
            if wanted is not None and not wanted: continue
            b=g.board(); moves=list(g.mainline_moves()); histories=[]
            for ply in range(len(moves)+1):
                m=moves[ply] if ply<len(moves) else None
                if wanted is None or ply in wanted:
                    row={'type':'position','game_id':gid,'source':source,'source_sha256':digest,'start_fen':g.board().fen(),'history_uci':histories.copy(),'ply':ply,'fen':b.fen(),'storm_colour':'white' if colour else 'black','storm_turn':b.turn==colour,'played_uci':m.uci() if m else None,'played_san':b.san(m) if m else None,'move_number':b.fullmove_number,'result':g.headers['Result']}
                    n=args.deep_nodes if wanted is not None else (args.site_nodes if gid.startswith('site') else args.holdout_nodes)
                    row.update(analyse(e,b,n))
                    if wanted is not None and m and not row.get('terminal'):
                        row['played_root']=analyse(e,b,n,[m])
                        alternatives=wanted[ply].get('alternatives',[])
                        row['alternatives']={u:analyse(e,b,n,[chess.Move.from_uci(u)]) for u in alternatives}
                    emit(row); total+=1
                if m:
                    assert m in b.legal_moves
                    b.push(m); histories.append(m.uci())
            print(json.dumps({'game':gid,'positions_done':total,'elapsed_s':round(time.perf_counter()-start,2)}),flush=True)
        emit({'type':'summary','positions':total,'elapsed_s':time.perf_counter()-start,'finished_utc':datetime.now(timezone.utc).isoformat()})

if __name__=='__main__': main()
