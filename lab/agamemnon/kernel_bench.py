"""Original incremental neural/pair kernels. Linux one-core cost experiment.
Includes both sum and squared-sum state and checks make/unmake-equivalent deltas.
Board/feature encoding is explicitly outside the compiled timing, not free in an engine.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json,platform,time
from pathlib import Path
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent

@njit
def refresh(ids,ns,w):
    h=w.shape[1];a=np.zeros((2,h),np.int32);sq=np.zeros((2,h),np.int64)
    for side in range(2):
        for k in range(ns[side]):
            for j in range(h):
                z=np.int32(w[ids[side,k],j]);a[side,j]+=z;sq[side,j]+=np.int64(z)*z
    return a,sq

@njit
def update(a,sq,rem,nr,add,na,w):
    aa=a.copy();ss=sq.copy()
    for side in range(2):
        for k in range(nr[side]):
            for j in range(w.shape[1]):
                z=np.int32(w[rem[side,k],j]);aa[side,j]-=z;ss[side,j]-=np.int64(z)*z
        for k in range(na[side]):
            for j in range(w.shape[1]):
                z=np.int32(w[add[side,k],j]);aa[side,j]+=z;ss[side,j]+=np.int64(z)*z
    return aa,ss

@njit
def value(a,sq,output,mode):
    v=0.0
    for side in range(2):
        sign=1.0 if side==0 else -1.0
        for j in range(a.shape[1]):
            z=min(512,max(0,a[side,j]+128)) if mode==1 else .5*(np.int64(a[side,j])*a[side,j]-sq[side,j])/256
            v+=sign*z*output[j]
    return v

@njit
def bench(ids,ns,rem,nr,add,na,w,output,loops,incremental,mode):
    check=0.0
    for _ in range(loops):
        a,sq=refresh(ids[0],ns[0],w)
        for i in range(1,len(ids)):
            if incremental and nr[i].sum()+na[i].sum()<ns[i].sum():a,sq=update(a,sq,rem[i],nr[i],add[i],na[i],w)
            else:a,sq=refresh(ids[i],ns[i],w)
            check+=value(a,sq,output,mode)
    return check

def prepare():
    import chess
    from representations import encode
    rng=np.random.default_rng(20260906);boards=[];special=dict(castle=0,ep=0,promotion=0)
    starts=[chess.STARTING_FEN,'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','4k3/P7/8/3pP3/8/8/7p/4K3 w - d6 0 1']
    for game in range(15):
        b=chess.Board(starts[game%3])
        for ply in range(80):
            boards.append(b.copy(stack=False));moves=list(b.legal_moves)
            if not moves:break
            move=next((m for m in moves if b.is_en_passant(m) or b.is_castling(m) or m.promotion),moves[int(rng.integers(len(moves)))])
            special['castle']+=b.is_castling(move);special['ep']+=b.is_en_passant(move);special['promotion']+=bool(move.promotion);b.push(move)
    dest=HERE/'kernel-data';dest.mkdir(exist_ok=False)
    for rep in ('piece','bucket','relative'):
        x=[encode(b,rep) for b in boards];n=len(x);cap=max(len(s) for pair in x for s in pair)
        arrays={k:np.zeros((n,2,cap),np.int32) for k in ('ids','rem','add')};counts={k:np.zeros((n,2),np.int32) for k in ('ns','nr','na')}
        for i,pair in enumerate(x):
            for side,z in enumerate(pair):
                old=set(x[i-1][side]) if i else set();cur=set(z)
                for key,nkey,values in [('ids','ns',z),('rem','nr',sorted(old-cur)),('add','na',sorted(cur-old))]:
                    arrays[key][i,side,:len(values)]=values;counts[nkey][i,side]=len(values)
        np.savez_compressed(dest/f'{rep}.npz',**arrays,**counts)
    (dest/'manifest.json').write_text(json.dumps(dict(states=len(boards),special=special,scope='Random legal trajectories including game boundaries. Feature encoding and extraction excluded from kernel timing.'),indent=2))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--cpu',type=int,default=0);a=ap.parse_args()
    if a.prepare:prepare();return
    assert platform.machine() in ('x86_64','AMD64') and os.name=='posix'
    os.sched_setaffinity(0,{a.cpu});started=time.perf_counter();rng=np.random.default_rng(20260906);results=[];checks=0
    for rep,features in [('piece',768),('bucket',6912),('relative',3468)]:
        z=np.load(HERE/f'kernel-data/{rep}.npz');args=[z[k] for k in ('ids','ns','rem','nr','add','na')];ids,ns,rem,nr,add,na=args
        for width in (32,128,256):
            w=rng.integers(-12,13,size=(features,width),dtype=np.int16);out=rng.normal(0,.01,width).astype(np.float32)
            ac,ss=refresh(ids[0],ns[0],w)
            for i in range(1,len(ids)):
                old=ac.copy();oldsq=ss.copy();ac,ss=update(ac,ss,rem[i],nr[i],add[i],na[i],w)
                ref,rsq=refresh(ids[i],ns[i],w);assert np.array_equal(ac,ref) and np.array_equal(ss,rsq)
                undo,usq=update(ac,ss,add[i],na[i],rem[i],nr[i],w);assert np.array_equal(undo,old) and np.array_equal(usq,oldsq);checks+=1
            for mode in (1,2):
                bench(*args,w,out,1,False,mode);bench(*args,w,out,1,True,mode);runs=[]
                for incremental in (False,True,True,False):
                    t=time.perf_counter();checksum=bench(*args,w,out,200,incremental,mode);dt=time.perf_counter()-t
                    runs.append(dict(incremental=incremental,seconds=dt,ns_per_transition_and_value=dt*1e9/(200*(len(ids)-1)),checksum=checksum))
                assert max(r['checksum'] for r in runs)-min(r['checksum'] for r in runs)<1e-5
                results.append(dict(representation=rep,width=width,mode='nn' if mode==1 else 'pair',embedding_bytes=w.nbytes,runs=runs))
    result=dict(platform=platform.platform(),affinity=list(os.sched_getaffinity(0)),checks=checks,elapsed_seconds=time.perf_counter()-started,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),results=results,scope='Original random-weight int16 kernels; sum and square state exact. No engine integration, learned quantization accuracy, full agent import or strength claim. Includes allocation/copy, excludes feature extraction and Python calls per node. Both modes maintain square sums: conservative NN cost.')
    (HERE/'kernel-linux.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(checks=checks,seconds=result['elapsed_seconds'],configurations=len(results))))
if __name__=='__main__':main()
