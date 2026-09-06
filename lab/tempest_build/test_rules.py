"""Integrated native and untouched-referee boundary checks for the fallback."""
import hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tempest'))
from lab.laptop_runner import apply_windows_affinity
if os.name=='nt':assert apply_windows_affinity(8)['applied']
sys.path.insert(0,str(HERE/'official-284724ab'))
from harness.referee import play_match
import chess,numpy as np
t=time.perf_counter();import agent,core_nb as c,history
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert c.NUMBA_READY and c.root_search_nb.nopython_signatures
cold=time.perf_counter()-t
def clear():
    for name in ('TT_KEY','TT_MOVE','TT_SCORE','TT_DEPTH','TT_GEN','KILLERS','HISTORY'):getattr(c,name).fill(0)
    history.reset()
def score(fen,depth):
    clear();p=from_fen(fen);bb,mb,st=c.pack_pos(p)
    arrays=(np.zeros((c.MAX_PLY,7),np.uint64),np.zeros((c.MAX_PLY,c.MAX_MOVES),np.int32),np.zeros((c.MAX_PLY,c.MAX_MOVES),np.int32),c.TT_KEY,c.TT_MOVE,c.TT_SCORE,c.TT_DEPTH,c.TT_GEN,c.TT_AGE,c.KILLERS,c.HISTORY,np.zeros(2,np.int64),np.zeros(1,np.int32))
    hist=np.zeros(1200,np.uint64);cap=600-chess.Board(fen).ply()
    before=[a.copy() for a in (bb,mb,st)]
    if depth is None:result=c.qsearch_nb(bb,mb,st,-c.INF,c.INF,0,hist,0,0,cap,10**7,True,*arrays)
    else:result=c.negamax_nb(bb,mb,st,depth,-c.INF,c.INF,0,hist,0,0,cap,10**7,True,*arrays)
    assert all(np.array_equal(a,b) for a,b in zip(before,(bb,mb,st)))
    return int(result)
class Script:
    def __init__(self,moves):self.moves=iter(moves);self.calls=0;self.stopped=False
    def start(self,budget):pass
    def move(self,fen,clock):self.calls+=1;return next(self.moves)
    def stop(self):self.stopped=True
checks=[]
for hm in (98,99,100):
    fen=f'7k/8/8/8/8/8/P7/R5K1 w - - {hm} 50'
    p=from_fen(fen);bb,mb,st=c.pack_pos(p);moves=np.array(generate_legal(p),np.int32)
    got=c.fifty_claim_nb(bb,mb,st,moves,len(moves),np.zeros(c.MAX_MOVES,np.int32),np.zeros(7,np.uint64))
    assert got==(hm>=100)
    q=score(fen,None);n=score(fen,1)
    assert (q==0)==(hm>=100)
    if hm>=100:assert n==0
    checks.append(dict(kind='fifty',halfmove=hm,q=q,depth1=n))
for fen,expected in [('7k/6Q1/5K2/8/8/8/8/8 b - - 100 51',-32000),('7k/5K2/6Q1/8/8/8/8/8 b - - 100 51',0)]:
    for depth in (None,1):assert score(fen,depth)==expected
    checks.append(dict(kind='mate_stalemate_precedence',fen=fen,expected=expected))
# Quiet mate on move 100 must be played, not auto-claimed at 99.
for hm in (98,99):
    fen=f'7k/8/5KQ1/8/8/8/8/8 w - - {hm} 50'
    clear();b=chess.Board(fen);u=agent.get_move(fen,1000);b.push_uci(u);assert b.is_checkmate(),u
    w,z=Script([u]),Script([]);o=play_match(w,z,120000,500,start_fen=fen)
    assert o.termination=='checkmate' and w.calls==1 and z.calls==0
    checks.append(dict(kind='quiet_mate',halfmove=hm,uci=u))
# The halfmove 99 position is actually served; at 100 it is not.
fen='7k/8/8/8/8/8/P7/R5K1 w - - 99 50'
w,z=Script(['a1b1']),Script([]);o=play_match(w,z,120000,500,start_fen=fen)
assert o.termination=='fifty_moves' and w.calls==1 and z.calls==0
w,z=Script([]),Script([]);o=play_match(w,z,120000,500,start_fen=fen.replace('99 50','100 51'))
assert o.termination=='fifty_moves' and w.calls==z.calls==0
# Repetition by intended eighth ply is no longer terminal on ply seven.
w,z=Script(['g1f3','f3g1','g1f3','f3g1']),Script(['g8f6','f6g8','g8f6','f6g8'])
o=play_match(w,z,120000,500)
assert o.termination=='threefold_repetition' and w.calls==4 and z.calls==4
checks.append(dict(kind='actual_third',white_calls=w.calls,black_calls=z.calls))
for fen,mate in [('7k/7p/8/8/8/8/P7/K7 b - - 0 300',False),('8/8/8/8/8/k7/2q5/K7 b - - 0 300',True)]:
    clear();b=chess.Board(fen);u=agent.get_move(fen,1000);b.push_uci(u)
    assert b.ply()==600 and b.is_checkmate()==mate
    w,z=Script([]),Script([u]);o=play_match(w,z,120000,500,start_fen=fen)
    assert o.termination==('checkmate' if mate else 'ply_cap')
    checks.append(dict(kind='absolute_cap',fen=fen,uci=u,termination=o.termination))
from lab.perft import POSITIONS
for name,fen,expected in POSITIONS:assert c.perft_pos(from_fen(fen),3)==expected[3]
result=dict(pass_all=True,cold_seconds=cold,checks=checks,perft_positions=len(POSITIONS),source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'tempest').glob('*.py')},scope='ARM native and exact new referee; Linux deployment still separate')
(HERE/'rules-test.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
