"""New v6 games, current-rule reference searches, full history and source identity."""
import argparse, hashlib, json, os, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import chess, chess.engine, chess.pgn
from lab.odin.development_review.review import pin_cpu4
from lab.odin.reference_review import score_info

EXE=Path('stockfish')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def terminal(b):
    outcome=b.outcome()
    if outcome:return outcome
    if b.is_repetition(3):return chess.Outcome(chess.Termination.THREEFOLD_REPETITION,None)
    if b.is_fifty_moves():return chess.Outcome(chess.Termination.FIFTY_MOVES,None)
    if b.ply()>=600:return chess.Outcome(chess.Termination.VARIANT_DRAW,None)
def reference(e,b,nodes,root_moves=None):
    o=terminal(b)
    if o:return dict(white_cp=0 if o.winner is None else (32000 if o.winner else -32000),terminal=o.termination.name,pv_uci=[],nodes=0)
    e.configure({'Clear Hash':None});last=None;total=0
    with e.analysis(b,chess.engine.Limit(nodes=nodes),game=object(),root_moves=root_moves) as stream:
        for item in stream:
            total=max(total,item.get('nodes',0))
            if 'score' in item and not item.get('lowerbound') and not item.get('upperbound'):last=dict(item)
    assert last is not None
    return dict(score_info(b,last),total_nodes=total,requested_nodes=nodes,exact_completed_iteration=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--round',type=int,required=True);ap.add_argument('--cpu',type=int,required=True);ap.add_argument('--deep',action='store_true');a=ap.parse_args()
    pin_cpu4(os.getpid(),a.cpu)
    outdir=HERE/'round38';outdir.mkdir(exist_ok=True)
    p=next((ROOT/'Chess_results_day3').glob(f'aichessathon-round-{a.round}-*.pgn'))
    with p.open(encoding='utf-8-sig') as f:g=chess.pgn.read_game(f)
    assert not g.errors;own=g.headers['White']=='Finlay Phillips'
    output=outdir/f'round-{a.round}-{"deep" if a.deep else "screen"}.jsonl'
    with chess.engine.SimpleEngine.popen_uci(str(EXE)) as e,output.open('x') as out:
        e.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
        def emit(r):out.write(json.dumps(r)+'\n');out.flush()
        emit(dict(type='metadata',headers=dict(g.headers),pgn_sha256=sha(p),reference_sha256=sha(EXE),script_sha256=sha(Path(__file__)),engine_version='Upload archive not recorded in PGN/log; version unverified',scope='diagnostics only; finite offline reference'))
        b=g.board();hist=[];clocks={True:120000,False:120000};began=time.perf_counter()
        if a.deep:
            rows=[json.loads(s) for s in (outdir/f'round-{a.round}-screen.jsonl').read_text().splitlines()]
            pos=[r for r in rows if r.get('type')=='position'];pairs=[]
            for x,y in zip(pos,pos[1:]):
                if x['own_turn'] and abs(x['reference']['white_cp'])<1500:
                    loss=(x['reference']['white_cp']-y['reference']['white_cp'])*(1 if own else -1)
                    if loss>=35:pairs.append((loss,x))
            selected=[r for _,r in sorted(pairs,key=lambda z:-z[0])[:6]]
            for r in selected:
                b=chess.Board(r['start_fen'])
                for u in r['history_uci']:b.push_uci(u)
                best=reference(e,b,2000000);played=reference(e,b,2000000,[chess.Move.from_uci(r['played_uci'])])
                emit(dict(type='deep',**{k:v for k,v in r.items() if k!='type'},best=best,played=played,loss_cp=(best['white_cp']-played['white_cp'])*(1 if own else -1)))
                print(a.round,r['san'],best['pv_uci'][:1],flush=True)
        else:
            nodes=list(g.mainline())
            for ply in range(len(nodes)+1):
                node=nodes[ply] if ply<len(nodes) else None
                assert b.is_valid() and (not node or terminal(b) is None)
                r=dict(type='position',round=a.round,ply=ply,fen=b.fen(),start_fen=g.board().fen(),history_uci=hist.copy(),own_turn=b.turn==own,own_colour='white' if own else 'black',time_left_ms=clocks[b.turn],played_uci=node.move.uci() if node else None,san=b.san(node.move) if node else None,reference=reference(e,b,100000))
                emit(r)
                if node:
                    assert node.move in b.legal_moves
                    if node.clock() is not None:clocks[b.turn]=round(node.clock()*1000)
                    hist.append(node.move.uci());b.push(node.move)
            assert terminal(b) is not None and terminal(b).result()==g.headers['Result']
        emit(dict(type='complete',seconds=time.perf_counter()-began))
    print(a.round,'complete',flush=True)
if __name__=='__main__':main()
