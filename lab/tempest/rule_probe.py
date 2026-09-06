"""Replay old/current terminal predicates; keep the official files untouched."""
import json,io,hashlib,sys,difflib
from pathlib import Path
import chess,chess.pgn
H=Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(H));from acquire import fetch
COMMIT='284724ab56cecb2a1a9a4e5769b4748adab4ed90'
def current(b):
    o=b.outcome()
    if o:return o.termination.name
    if b.is_repetition(3):return 'THREEFOLD_REPETITION'
    if b.is_fifty_moves():return 'FIFTY_MOVES'
    if b.ply()>=600:return 'PLY_CAP'
    return None
def legacy(b):
    o=b.outcome(claim_draw=True)
    return o.termination.name if o else ('PLY_CAP' if b.ply()>=600 else None)
def main():
    text=fetch('https://raw.githubusercontent.com/advitrocks9/aichessathon-starter/'+COMMIT+'/harness/referee.py','referee-'+COMMIT+'.py')
    assert 'finish = board.outcome()' in text and 'if board.is_repetition(3):' in text and 'if board.is_fifty_moves():' in text
    old=(R/'lab/odin/official-harness-91f70e54/harness/referee.py').read_text();(H/'referee-diff.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='91f70e54/harness/referee.py',tofile=COMMIT+'/harness/referee.py')))
    b=chess.Board()
    for u in ['g1f3','g8f6','f3g1','f6g8','g1f3','g8f6','f3g1']:b.push_uci(u)
    fixtures=[('intended-third',b.copy()),('halfmove99',chess.Board('7k/8/8/8/8/8/P7/R5K1 w - - 99 50')),('halfmove100',chess.Board('7k/8/8/8/8/8/P7/R5K1 w - - 100 51'))]
    b.push_uci('f6g8');fixtures.append(('actual-third',b.copy()))
    fixtures.append(('mate-precedes-clock',chess.Board('7k/6Q1/5K2/8/8/8/8/8 b - - 100 51')))
    probes=[dict(id=k,fen=b.fen(),history=[m.uci() for m in b.move_stack],legacy=legacy(b),current=current(b)) for k,b in fixtures]
    assert probes[0]['current'] is None and probes[0]['legacy']=='THREEFOLD_REPETITION'
    assert probes[1]['current'] is None and probes[1]['legacy']=='FIFTY_MOVES'
    assert probes[2]['current']=='FIFTY_MOVES' and probes[3]['current']=='THREEFOLD_REPETITION' and probes[4]['current']=='CHECKMATE'
    games=[]
    for m in json.loads((H/'public/games.json').read_text()):
        if 'pgn' not in m:continue
        g=chess.pgn.read_game(io.StringIO((H/m['pgn']).read_text()));b=g.board();early=[]
        for ply,n in enumerate(g.mainline()):
            if current(b):early.append(dict(ply=ply,outcome=current(b)))
            b.push(n.move)
        games.append(dict(game_id=m['game_id'],early_current=early[:1],final=current(b)))
    result=dict(commit=COMMIT,referee_sha256=hashlib.sha256(text.encode()).hexdigest(),fixtures=probes,games=games,scope='Predicate replay verified against exact fetched official source, not a full sandbox match.')
    (H/'rule-probe.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
