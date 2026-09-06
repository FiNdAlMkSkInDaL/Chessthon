"""Check every skipped SEE call against the actual legal swap-off evaluator."""
import argparse,os,sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
ap=argparse.ArgumentParser();ap.add_argument('--promotion-only',action='store_true');args=ap.parse_args()
from lab.laptop_runner import apply_windows_affinity,apply_windows_memory_job
assert apply_windows_affinity(4)['applied'];assert apply_windows_memory_job(2*1024**3)['applied']
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
sys.path.insert(0,str(ROOT/'odin_see_fast'))
import agent,core_nb as c,numpy as np,chess
from board_nb import from_fen
assert c.NUMBA_READY
fens=[]
for p in ([] if args.promotion_only else (ROOT/'lab/odin/new_games').glob('round-*-screen.jsonl')):
    for s in p.read_text().splitlines():
        r=json.loads(s)
        if r.get('type')=='position':fens.append(r['fen'])
if not args.promotion_only:
    for line in (ROOT/'lab/odin/training/corpus-20k.jsonl').read_text().splitlines()[::4]:fens.append(json.loads(line)['fen'])
# Explicit low-value capturer followed by a promoting pawn recapture.
edge=chess.Board('7k/8/8/8/8/8/1pN5/r6K w - - 0 1')
fens.extend([edge.fen(),edge.mirror().fen()])
positions=captures=skipped=backrank=0
for fen in dict.fromkeys(fens):
    board=chess.Board(fen)
    if not board.is_valid():continue
    bb,mb,st=c.pack_pos(from_fen(fen));moves=np.zeros(c.MAX_MOVES,dtype=np.int32);scratch=moves.copy()
    n=c.gen_legal(bb,mb,st,moves,scratch);positions+=1
    if fen in (edge.fen(),edge.mirror().fen()):
        target='c2a1' if board.turn else 'c7a8'
        found=[m for m in moves[:n] if c.m_from(m)==chess.Move.from_uci(target).from_square and c.m_to(m)==chess.Move.from_uci(target).to_square]
        assert len(found)==1 and c.see_nb(bb,mb,st,found[0])==-600,(fen,found)
    for move in moves[:n]:
        if not c.m_cap(move) or c.m_promo(move):continue
        captures+=1;to=c.m_to(move);attacker=int(mb[c.m_from(move)])%6
        if to<8 or to>=56:backrank+=1;continue
        if c.SEE_V[c.victim_pt(mb,move)]>=c.SEE_V[attacker]:
            score=int(c.see_nb(bb,mb,st,move));assert score>=0,(fen,int(move),score);skipped+=1
result={'pass':True,'positions':positions,'captures':captures,'safely_skipped_see':skipped,'backrank_cases_retained':backrank,'source_sha256':hashlib.sha256((ROOT/'odin_see_fast/core_nb.py').read_bytes()).hexdigest()}
(ROOT/'lab/odin/fast'/('see-promotion-bound-test.json' if args.promotion_only else 'see-bound-test.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
