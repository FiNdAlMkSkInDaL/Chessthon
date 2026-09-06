"""Original exhaustive retrograde KQK/KRK DTM, independent of reference engines.

State = side*262144 + attacking_king*4096 + major*64 + defending_king.
Side 0 is attacker to move. 255 = invalid/draw, all other values = plies to
mate with attacker minimizing and defender maximizing. Draw capture edges
remain in the defender's degree and prevent false wins.
"""
import os
for k in ('NUMBA_NUM_THREADS','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import json,time,hashlib
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent
N=524288
@njit
def adjacent(a,b):return max(abs(a//8-b//8),abs(a%8-b%8))<=1
@njit
def attacked(ak,m,dk,queen):
    dr=dk//8-m//8;df=dk%8-m%8
    if not (dr==0 or df==0 or (queen and abs(dr)==abs(df))):return False
    sr=(dr>0)-(dr<0);sf=(df>0)-(df<0);r=m//8+sr;f=m%8+sf
    while r*8+f!=dk:
        if r*8+f==ak:return False
        r+=sr;f+=sf
    return True
@njit
def valid(ak,m,dk,side,queen):
    return ak!=m and ak!=dk and m!=dk and not adjacent(ak,dk) and (side==1 or not attacked(ak,m,dk,queen))
@njit
def predecessors(ak,m,dk,side,queen,out):
    n=0
    if side==0:
        # Last move was the defending king.
        for dr in range(-1,2):
            for df in range(-1,2):
                if dr==0 and df==0:continue
                r=dk//8+dr;f=dk%8+df
                if 0<=r<8 and 0<=f<8:
                    old=r*8+f
                    if valid(ak,m,old,1,queen):out[n]=262144+ak*4096+m*64+old;n+=1
    else:
        for dr in range(-1,2):
            for df in range(-1,2):
                if dr==0 and df==0:continue
                r=ak//8+dr;f=ak%8+df
                if 0<=r<8 and 0<=f<8:
                    old=r*8+f
                    if valid(old,m,dk,0,queen):out[n]=old*4096+m*64+dk;n+=1
        for dr in range(-1,2):
            for df in range(-1,2):
                if (dr==0 and df==0) or (not queen and dr!=0 and df!=0):continue
                r=m//8+dr;f=m%8+df
                while 0<=r<8 and 0<=f<8:
                    old=r*8+f
                    if old==ak or old==dk:break
                    if valid(ak,old,dk,0,queen):out[n]=ak*4096+old*64+dk;n+=1
                    r+=dr;f+=df
    return n
@njit
def build(queen):
    dtm=np.full(N,255,np.uint8);degree=np.zeros(N,np.uint8);legal=np.zeros(N,np.uint8);queue=np.empty(N,np.int32);end=0
    for ak in range(64):
        for m in range(64):
            for dk in range(64):
                for side in range(2):
                    if not valid(ak,m,dk,side,queen):continue
                    idx=side*262144+ak*4096+m*64+dk;legal[idx]=1
                    if side==0:continue
                    deg=0
                    for dr in range(-1,2):
                        for df in range(-1,2):
                            if dr==0 and df==0:continue
                            r=dk//8+dr;f=dk%8+df
                            if not (0<=r<8 and 0<=f<8):continue
                            to=r*8+f
                            if adjacent(ak,to):continue
                            if to==m or not attacked(ak,m,to,queen):deg+=1
                    degree[idx]=deg
                    if deg==0 and attacked(ak,m,dk,queen):dtm[idx]=0;queue[end]=idx;end+=1
    ptr=0;pred=np.empty(40,np.int32);last=-1
    while ptr<end:
        idx=queue[ptr];ptr+=1;side=idx//262144;rest=idx%262144;ak=rest//4096;m=(rest//64)%64;dk=rest%64;d=int(dtm[idx])
        assert d>=last;last=d
        n=predecessors(ak,m,dk,side,queen,pred)
        for i in range(n):
            p=pred[i]
            if dtm[p]!=255:continue
            if side==1:
                assert d+1<255;dtm[p]=d+1;queue[end]=p;end+=1
            else:
                assert degree[p]>0;degree[p]-=1
                if degree[p]==0:dtm[p]=d+1;queue[end]=p;end+=1
    return dtm,legal,end,last
def main():
    out=HERE/'three-piece';out.mkdir(exist_ok=False);start=time.perf_counter();tables={};report={}
    for name,queen in [('queen',True),('rook',False)]:
        dtm,legal,n,maxd=build(queen);tables[name]=dtm
        np.save(out/(name+'-legal.npy'),legal)
        report[name]=dict(legal_states=int(legal.sum()),winning_states=n,draw_states=int(legal.sum())-n,max_dtm=maxd)
        print(name,report[name],flush=True)
    np.savez_compressed(out/'three_piece_dtm.npz',**tables)
    report.update(seconds=time.perf_counter()-start,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),data_sha256=hashlib.sha256((out/'three_piece_dtm.npz').read_bytes()).hexdigest(),provenance='Original exhaustive legal-state retrograde; no reference engine data, code, or published tablebase.')
    (out/'generation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
