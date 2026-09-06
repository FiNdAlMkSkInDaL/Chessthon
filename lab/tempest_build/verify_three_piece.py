"""Exhaustive forward Bellman checks using the independently tested v6 generator."""
import os,sys,json,time,hashlib
from pathlib import Path
for k in ('NUMBA_NUM_THREADS','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tempest_exact'))
from lab.laptop_runner import apply_windows_affinity
if os.name=='nt':assert apply_windows_affinity(6)['applied']
import numpy as np,chess
from numba import njit
import agent,core_nb as c,endgame_exact as eg
from board_nb import from_fen,move_uci
assert c.NUMBA_READY and Path(c.__file__).resolve().parent==ROOT/'tempest_exact'
@njit
def verify(dtm,legal,typ):
    bb=np.zeros(12,np.uint64);mb=np.full(64,-1,np.int8);st=np.zeros(12,np.uint64);moves=np.zeros(c.MAX_MOVES,np.int32);scratch=moves.copy();edges=0;count=0
    for idx in range(len(dtm)):
        side=idx//262144;rest=idx%262144;ak=rest//4096;m=(rest//64)%64;dk=rest%64
        bb.fill(0);mb.fill(-1);st.fill(0)
        bb[5]=np.uint64(1)<<np.uint64(ak);bb[typ]=np.uint64(1)<<np.uint64(m);bb[11]=np.uint64(1)<<np.uint64(dk)
        mb[ak]=5;mb[m]=typ;mb[dk]=11
        st[c.OCC_W]=bb[5]|bb[typ];st[c.OCC_B]=bb[11];st[c.OCC]=st[c.OCC_W]|st[c.OCC_B];st[c.SIDE]=side;st[c.EP]=64;st[c.FULL]=1
        valid=ak!=m and ak!=dk and m!=dk and not bool(c.KING_A[ak]&bb[11])
        if valid and side==0:valid=not c.in_check_nb(bb,st,1)
        assert valid==bool(legal[idx])
        if not valid:assert dtm[idx]==255;continue
        count+=1;n=c.gen_legal(bb,mb,st,moves,scratch);edges+=n
        if n==0:
            expect=0 if c.in_check_nb(bb,st,side) else 255
        else:
            low=255;high=0;all_win=True
            for i in range(n):
                mv=moves[i];frm=c.m_from(mv);to=c.m_to(mv)
                if side==1 and to==m:d=255
                else:
                    aa=to if side==0 and frm==ak else ak
                    mm=to if side==0 and frm==m else m
                    dd=to if side==1 else dk
                    child=(1-side)*262144+aa*4096+mm*64+dd
                    assert legal[child]
                    d=int(dtm[child])
                low=min(low,d);high=max(high,d);all_win=all_win and d!=255
            expect=(low+1 if low<255 else 255) if side==0 else (high+1 if all_win else 255)
        assert int(dtm[idx])==expect,(idx,int(dtm[idx]),expect)
    return count,edges
start=time.perf_counter();report={}
for typ,name in [(4,'queen'),(3,'rook')]:
    legal=np.load(HERE/f'three-piece/{name}-legal.npy');dtm=eg._TABLES[typ+1]
    count,edges=verify(dtm,legal,typ);report[name]=dict(states=count,legal_edges=edges)
    rng=np.random.default_rng(600+typ);ids=rng.choice(np.flatnonzero(legal),2000,replace=False)
    for idx in ids:
        side=idx//262144;rest=idx%262144;ak=rest//4096;m=(rest//64)%64;dk=rest%64
        b=chess.Board(None);b.set_piece_at(int(ak),chess.Piece(chess.KING,True));b.set_piece_at(int(m),chess.Piece(typ+1,True));b.set_piece_at(int(dk),chess.Piece(chess.KING,False));b.turn=not side
        assert b.is_valid()
        pos=from_fen(b.fen());bb,mb,st=c.pack_pos(pos);out=np.zeros(256,np.int32);scratch=out.copy();n=c.gen_legal(bb,mb,st,out,scratch)
        assert {move_uci(int(v)) for v in out[:n]}=={mv.uci() for mv in b.legal_moves}
        if not b.is_game_over():
            before=b.fen();u=eg.choose_exact(b);assert u and chess.Move.from_uci(u) in b.legal_moves;assert b.fen()==before
            mirror=b.mirror();v=eg.choose_exact(mirror);assert v and chess.Move.from_uci(v) in mirror.legal_moves
    print(name,report[name],flush=True)
report.update(pass_all=True,python_chess_positions=4000,seconds=time.perf_counter()-start,table_sha256=hashlib.sha256((ROOT/'tempest_exact/three_piece_dtm.npz').read_bytes()).hexdigest(),source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'tempest_exact').iterdir() if p.is_file()})
(HERE/'three-piece/verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
