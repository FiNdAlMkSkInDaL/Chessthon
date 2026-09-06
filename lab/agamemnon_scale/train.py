"""Original contiguous sparse training kernel and controlled million-row sweep."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,json,sys,time
from pathlib import Path
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'lab/agamemnon'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OLD))
from representations import forward,batch_grad,adam,metrics,sha,verify

@njit
def contiguous_grad(x,counts,phase,y,weights,ids,w,bias,out,mode):
    gw=np.zeros_like(w);gb=np.zeros_like(bias);go=np.zeros_like(out)
    h=w.shape[1];total=0.;loss=0.
    sums=np.empty((2,h),np.float32);zs=np.empty((2,h),np.float32);dzs=np.empty(h,np.float64)
    for i in ids:total+=weights[i]
    for i in ids:
        pred=0.
        for side in range(2):
            for j in range(h):sums[side,j]=bias[j]
            for k in range(counts[i,side]):
                idx=x[i,side,k]
                for j in range(h):sums[side,j]+=w[idx,j]
            sign=1. if side==0 else -1.
            for j in range(h):
                a=sums[side,j];z=a if mode==0 else min(2.,max(0.,a));zs[side,j]=z
                pred+=sign*z*(phase[i]*out[j,0]+(1-phase[i])*out[j,1])
        err=pred-y[i];wt=weights[i]/total;loss+=wt*(.5*err*err if abs(err)<=1 else abs(err)-.5)
        d=min(1.,max(-1.,err))*wt
        for side in range(2):
            sign=1. if side==0 else -1.
            for j in range(h):
                a=sums[side,j];dz=d*sign*(phase[i]*out[j,0]+(1-phase[i])*out[j,1])
                go[j,0]+=d*sign*zs[side,j]*phase[i];go[j,1]+=d*sign*zs[side,j]*(1-phase[i])
                if mode==1 and (a<=0 or a>=2):dz=0.
                gb[j]+=dz;dzs[j]=dz
            for k in range(counts[i,side]):
                idx=x[i,side,k]
                for j in range(h):gw[idx,j]+=dzs[j]
    return loss,gw,gb,go

def check_kernel():
    z=np.load(OLD/'public-data/transfer-piece.npz');rng=np.random.default_rng(909)
    args=[z[k] for k in ('x','counts','phase')]+[(z['y']-z['base'])/400,z['weights'],np.arange(256)]
    checks=[]
    for width,mode in ((1,0),(32,1),(128,1),(256,1)):
        par=[rng.normal(0,.025,(768,width)).astype(np.float32),np.full(width,.5,np.float32),rng.normal(0,.04,(width,2)).astype(np.float32)]
        a=batch_grad(*args,*par,mode);b=contiguous_grad(*args,*par,mode)
        maximum=max(float(np.max(np.abs(x-y))) for x,y in zip(a,b));assert maximum<2e-6,maximum
        times=[]
        for fn in (batch_grad,contiguous_grad):
            st=time.perf_counter()
            for _ in range(20):fn(*args,*par,mode)
            times.append(time.perf_counter()-st)
        checks.append(dict(width=width,max_gradient_difference=maximum,old_seconds=times[0],new_seconds=times[1],speedup=times[0]/times[1]))
    return checks

def fit(data,dev,cap,width,seed,epochs,init=None,rate=.002):
    mode=int(width>1);rng=np.random.default_rng(seed)
    ids=np.random.default_rng(2026090603).permutation(len(data['y']))[:cap]
    target=(data['y']-data['base'])/400
    par=[rng.normal(0,.025,(768,width)).astype(np.float32),np.full(width,.5 if mode else 0,np.float32),rng.normal(0,.04,(width,2)).astype(np.float32)] if init is None else [p.copy() for p in init]
    if not mode and init is None:par[0][:]=0;par[2][:]=1
    m=[np.zeros_like(p) for p in par];v=[np.zeros_like(p) for p in par];step=0;best=(float('inf'),0,None);curve=[];start=time.perf_counter()
    for epoch in range(1,epochs+1):
        rng.shuffle(ids)
        for pos in range(0,len(ids),256):
            _,*g=contiguous_grad(data['x'],data['counts'],data['phase'],target,data['weights'],ids[pos:pos+256],*par,mode);step+=1
            for j,p in enumerate(par):
                if mode==0 and j>0:continue
                adam(p,g[j],m[j],v[j],step,rate,.02)
        pred=dev['base']+400*forward(dev['x'],dev['counts'],dev['phase'],*par,mode)
        score=metrics(dev['y'],pred)['mae'];curve.append(dict(epoch=epoch,mae=score,seconds=time.perf_counter()-start))
        if score<best[0]:best=(score,epoch,[p.copy() for p in par])
    par=best[2];pred=dev['base']+400*forward(dev['x'],dev['counts'],dev['phase'],*par,mode)
    met={}
    for name,mask in [('all',np.ones(len(pred),bool)),('quiet',dev['quiet']),('guard',~dev['quiet']),('endgame',dev['phase']<=.25)]:met[name]=dict(pesto=metrics(dev['y'][mask],dev['base'][mask]),model=metrics(dev['y'][mask],pred[mask]))
    return par,dict(width=width,seed=seed,cap=cap,selected_epoch=best[1],curve=curve,metrics=met,seconds=time.perf_counter()-start),pred

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lane',type=int,required=True);ap.add_argument('--cpu',type=int,required=True);a=ap.parse_args()
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(a.cpu)['applied'];dest=HERE/f'train/lane{a.lane}';dest.mkdir(parents=True,exist_ok=False)
    width=(1,32,128,256)[a.lane];identity=sha(__file__);checks=check_kernel()
    data={k:np.load(HERE/f'data/{k}.npy',mmap_mode='r') for k in ('x','counts','phase','base','y','weights','quiet')};dev=dict(np.load(HERE/'data/development.npz'))
    cross=np.load(OLD/'public-data/transfer-piece.npz');tr=cross['split']==0;va=~tr
    transfer={k:cross[k][tr] for k in data};td={k:cross[k][va] for k in data}
    control=np.load(OLD/'data/piece.npz')['base'][va]
    with (dest/'results.jsonl').open('x') as f:
        def emit(r):f.write(json.dumps(r)+'\n');f.flush();print(json.dumps(r if r['type']!='trial' else {k:r[k] for k in ('type','width','cap','seed','selected_epoch','seconds','metrics')}),flush=True)
        emit(dict(type='metadata',script_sha256=identity,kernel_checks=checks,original_checks=verify(),data_manifest_sha256=sha(HERE/'data/manifest.json'),width=width,caps=[128000,512000,1000000],seeds=[260908,260909],epochs=8,adapt_epochs=45))
        for cap in (128000,512000,1000000):
            for seed in (260908,260909):
                par,r,pred=fit(data,dev,cap,width,seed,8);tag=f'w{width}-n{cap}-s{seed}'
                np.savez_compressed(dest/f'{tag}-public.npz',w=par[0],bias=par[1],out=par[2]);emit(dict(type='trial',**r))
                adapted,rr,pp=fit(transfer,td,len(transfer['y']),width,seed,45,par,.001)
                rr['pretrain_cap']=cap;rr['tempest']=metrics(td['y'],control)
                np.savez_compressed(dest/f'{tag}-adapted.npz',w=adapted[0],bias=adapted[1],out=adapted[2],pred=pp)
                emit(dict(type='adaptation',**rr))
        assert sha(__file__)==identity;emit(dict(type='complete'))
if __name__=='__main__':main()
