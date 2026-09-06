"""Single-thread finite reference; discovery only. Full available PGN history."""
import sys,os,json,hashlib,io,time,argparse
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(R))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(6)['applied']
import chess,chess.pgn,chess.engine
from lab.odin.new_games.review_new import reference
EXE=Path('C:/Users/finla/AppData/Local/ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe')
ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['corpus','games','choices'],required=True);args=ap.parse_args()
cases=json.loads((H/'corpus-v1.json').read_text());splits={r['game_id']:r for r in json.loads((H/'split-manifest.json').read_text())}
if (H/'opponent-critical.json').exists():cases+=json.loads((H/'opponent-critical.json').read_text())
def board(c):
    b=chess.Board(c['start_fen'])
    for u in c['history_uci']:b.push_uci(u)
    assert b.fen()==c['fen'];return b
outpath=H/('reference-'+args.mode+'.jsonl');done=set()
if outpath.exists():
    for s in outpath.read_text().splitlines():
        r=json.loads(s);done.add(r.get('key'))
with chess.engine.SimpleEngine.popen_uci(str(EXE)) as e,outpath.open('a') as out:
    e.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
    def emit(r):out.write(json.dumps(r)+'\n');out.flush()
    emit(dict(type='metadata',mode=args.mode,exe_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cpu=6,hash_mb=64,threads=1,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    if args.mode=='corpus':
        for c in cases:
            if c['split']!='discovery' or c['id'] in done:continue
            b=board(c);best=reference(e,b,1000000)
            played=reference(e,b,300000,[chess.Move.from_uci(c['played_uci'])]) if c.get('played_uci') else None
            emit(dict(type='reference',key=c['id'],id=c['id'],best=best,played=played));print(c['id'],flush=True)
    elif args.mode=='games':
        manifest=json.loads((H/'public/games.json').read_text())
        for m in manifest:
            if 'pgn' not in m or splits[m['game_id']]['split']!='discovery':continue
            g=chess.pgn.read_game(io.StringIO((H/m['pgn']).read_text()));b=g.board();prior=[];clocks={True:120000.,False:120000.}
            for ply,n in enumerate(g.mainline()):
                key=m['game_id']+'-'+str(ply);clock_before=clocks[b.turn]
                elapsed=clock_before+500-n.clock()*1000 if n.clock() is not None else None
                if key not in done and ply<100 and b.outcome(claim_draw=True) is None:
                    best=reference(e,b,50000);played=reference(e,b,50000,[n.move]);sign=1 if b.turn else -1
                    emit(dict(type='screen',key=key,game_id=m['game_id'],ply=ply,absolute_ply=b.ply(),fen=b.fen(),color='white' if b.turn else 'black',player=g.headers['White' if b.turn else 'Black'],opponent=g.headers['Black' if b.turn else 'White'],uci=n.move.uci(),san=b.san(n.move),best=best,played=played,loss_cp=sign*(best['white_cp']-played['white_cp']),pieces=len(b.piece_map()),legal_moves=b.legal_moves.count(),check=b.is_check(),zeroing=b.is_zeroing(n.move),clock_before_ms=clock_before,elapsed_ms=elapsed))
                if n.clock() is not None:clocks[b.turn]=n.clock()*1000
                prior.append(n.move.uci());b.push(n.move)
            print(m['game_id'],flush=True)
    else:
        targets={}
        for p in H.glob('*-probes.jsonl'):
            for s in p.read_text().splitlines():
                r=json.loads(s)
                if r.get('type')=='probe':targets.setdefault(r['id'],set()).add(r['uci'])
        for c in cases:
            if c['split']=='discovery' and c.get('played_uci'):
                targets.setdefault(c['id'],set()).add(c['played_uci'])
            for u in sorted(targets.get(c['id'],[])):
                key=c['id']+':'+u
                if key in done:continue
                b=board(c);result=reference(e,b,1000000,[chess.Move.from_uci(u)])
                emit(dict(type='choice',key=key,id=c['id'],uci=u,reference=result));print(key,flush=True)
