"""Original integer accumulator feasibility prototype using OUR prior weights.
No engine integration or strength claim. Board differences are an offline oracle.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import sys,json,time,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(R))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(8)['applied']
import numpy as np,chess
from numba import njit
@njit
def refresh(ids,n,w,b):
    acc=b.astype(np.int32).copy()
    for i in range(n):
        for j in range(len(acc)):acc[j]+=np.int32(w[ids[i],j])
    return acc
@njit
def delta(acc,removed,nr,added,na,w):
    result=acc.copy()
    for i in range(nr):
        for j in range(len(result)):result[j]-=np.int32(w[removed[i],j])
    for i in range(na):
        for j in range(len(result)):result[j]+=np.int32(w[added[i],j])
    return result
@njit
def bench(ids,ns,removed,nrs,added,nas,w,b,loops,incremental):
    checksum=0
    for _ in range(loops):
        acc=refresh(ids[0],ns[0],w,b)
        for i in range(1,len(ns)):
            acc=delta(acc,removed[i],nrs[i],added[i],nas[i],w) if incremental else refresh(ids[i],ns[i],w,b)
            checksum+=acc[0]
    return checksum
def encode(b):return set(((0 if p.color else 6)+p.piece_type-1)*64+s for s,p in b.piece_map().items())
def main():
    wp=R/'lab/odin/fast/network-training/weights.npz';z=np.load(wp);w=z['embedding'];bias=z['bias'];rng=np.random.default_rng(20260906)
    starts=[chess.STARTING_FEN,'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','4k3/P7/8/3pP3/8/8/7p/4K3 w - d6 0 1']
    ids=[];rem=[];add=[];ns=[];nr=[];na=[];special={'castle':0,'ep':0,'promotion':0};checks=0
    for game in range(30):
        b=chess.Board(starts[game%3]);prev=set()
        for ply in range(100):
            cur=encode(b);r=sorted(prev-cur);a=sorted(cur-prev)
            ids.append(sorted(cur)+[0]*(32-len(cur)));ns.append(len(cur));rem.append(r+[0]*(32-len(r)));nr.append(len(r));add.append(a+[0]*(32-len(a)));na.append(len(a));prev=cur
            moves=list(b.legal_moves)
            if not moves:break
            # Ensure special edges are covered, otherwise deterministic random legal play.
            m=next((m for m in moves if b.is_en_passant(m) or b.is_castling(m) or m.promotion),moves[int(rng.integers(len(moves)))])
            special['castle']+=b.is_castling(m);special['ep']+=b.is_en_passant(m);special['promotion']+=bool(m.promotion);b.push(m)
    ids,ns,rem,nr,add,na=[np.asarray(x,dtype=np.int32) for x in (ids,ns,rem,nr,add,na)]
    # Game-boundary transitions must remove the previous board, not a zero accumulator.
    for i in range(1,len(ns)):
        r=sorted(set(ids[i-1,:ns[i-1]])-set(ids[i,:ns[i]]));a=sorted(set(ids[i,:ns[i]])-set(ids[i-1,:ns[i-1]]));rem[i]=r+[0]*(32-len(r));nr[i]=len(r);add[i]=a+[0]*(32-len(a));na[i]=len(a)
    acc=refresh(ids[0],ns[0],w,bias);maximum=0
    for i in range(1,len(ns)):
        prev=acc.copy();acc=delta(acc,rem[i],nr[i],add[i],na[i],w)
        assert np.array_equal(acc,refresh(ids[i],ns[i],w,bias));assert np.array_equal(delta(acc,add[i],na[i],rem[i],nr[i],w),prev);checks+=1;maximum=max(maximum,int(np.max(np.abs(acc))))
    bench(ids,ns,rem,nr,add,na,w,bias,1,True);bench(ids,ns,rem,nr,add,na,w,bias,1,False);runs=[]
    for mode in [False,True,True,False]:
        t=time.perf_counter();s=bench(ids,ns,rem,nr,add,na,w,bias,200,mode);runs.append(dict(incremental=mode,seconds=time.perf_counter()-t,checksum=int(s)))
    assert len(set(r['checksum'] for r in runs))==1
    result=dict(weight_sha256=hashlib.sha256(wp.read_bytes()).hexdigest(),shape=list(w.shape),dtype='int16 weights / int32 accumulator',state_checks=checks,special_moves=special,max_abs_accumulator=maximum,embedding_bytes=w.nbytes,accumulator_bytes=16*4*2*96,runs=runs,scope='Isolated ARM compiled loops, no Python board-delta cost in timing; does NOT measure search throughput, Linux import or playing strength. Reuses our rejected small-data network only as original test weights.')
    (H/'accumulator-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
