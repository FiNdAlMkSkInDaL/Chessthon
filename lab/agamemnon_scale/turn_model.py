"""Original mover/opponent neural heads: colour symmetry without fixed tempo."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,json,sys,time
from pathlib import Path
import numpy as np
from numba import njit
from train import HERE,ROOT,OLD,adam,metrics,sha,forward
sys.path.insert(0,str(ROOT/'tempest_exact'))
from eval_nb import MG_TABLE,EG_TABLE
MG=np.array(MG_TABLE,np.float64).reshape(-1);EG=np.array(EG_TABLE,np.float64).reshape(-1)
for p in range(6,12):MG[p*64:(p+1)*64]*=-1;EG[p*64:(p+1)*64]*=-1
@njit
def infer_turn(x,counts,phase,base):
    """Input cache stores PeSTO plus signed10cp tempo; recover the FEN turn."""
    turns=np.empty(len(base),np.int8)
    for i in range(len(base)):
        mg=0.;eg=0.
        for k in range(counts[i,0]):idx=x[i,0,k];mg+=MG[idx];eg+=EG[idx]
        delta=base[i]-(mg*phase[i]+eg*(1-phase[i]));assert abs(abs(delta)-10)<.02
        turns[i]=1 if delta>0 else -1
    return turns
@njit
def turn_forward(x,counts,phase,turn,w,bias,out):
    result=np.zeros(len(x),np.float32);h=w.shape[1];acc=np.empty(h,np.float32)
    for i in range(len(x)):
        for view in range(2):
            role=0 if (view==0)==(turn[i]==1) else 2
            for j in range(h):acc[j]=bias[j]
            for k in range(counts[i,view]):
                for j in range(h):acc[j]+=w[x[i,view,k],j]
            for j in range(h):result[i]+=turn[i]*min(2.,max(0.,acc[j]))*(phase[i]*out[j,role]+(1-phase[i])*out[j,role+1])
    return result
@njit
def turn_grad(x,counts,phase,turn,y,weights,ids,w,bias,out):
    gw=np.zeros_like(w);gb=np.zeros_like(bias);go=np.zeros_like(out);h=w.shape[1]
    sums=np.empty((2,h),np.float32);zs=np.empty((2,h),np.float32);dzs=np.empty(h,np.float64);loss=0.;total=0.
    for i in ids:total+=weights[i]
    for i in ids:
        pred=0.
        for view in range(2):
            role=0 if (view==0)==(turn[i]==1) else 2
            for j in range(h):sums[view,j]=bias[j]
            for k in range(counts[i,view]):
                idx=x[i,view,k]
                for j in range(h):sums[view,j]+=w[idx,j]
            for j in range(h):
                z=min(2.,max(0.,sums[view,j]));zs[view,j]=z;pred+=turn[i]*z*(phase[i]*out[j,role]+(1-phase[i])*out[j,role+1])
        err=pred-y[i];wt=weights[i]/total;loss+=wt*(.5*err*err if abs(err)<=1 else abs(err)-.5);d=min(1.,max(-1.,err))*wt
        for view in range(2):
            role=0 if (view==0)==(turn[i]==1) else 2
            for j in range(h):
                a=sums[view,j];dz=d*turn[i]*(phase[i]*out[j,role]+(1-phase[i])*out[j,role+1])
                go[j,role]+=d*turn[i]*zs[view,j]*phase[i];go[j,role+1]+=d*turn[i]*zs[view,j]*(1-phase[i])
                if a<=0 or a>=2:dz=0.
                gb[j]+=dz;dzs[j]=dz
            for k in range(counts[i,view]):
                idx=x[i,view,k]
                for j in range(h):gw[idx,j]+=dzs[j]
    return loss,gw,gb,go
def verify_turn():
    rng=np.random.default_rng(88);x=np.array([[[0,1,2],[2,3,4]],[[0,3,4],[1,2,4]]],np.int32);counts=np.full((2,2),3,np.int32);phase=np.array([.3,.8],np.float32);turn=np.array([1,-1],np.int8);y=np.array([.1,-.2],np.float32);weights=np.ones(2,np.float32);ids=np.arange(2)
    par=[rng.normal(0,.04,(5,4)).astype(np.float32),np.full(4,.5,np.float32),rng.normal(0,.1,(4,4)).astype(np.float32)]
    loss,*g=turn_grad(x,counts,phase,turn,y,weights,ids,*par);checks=0
    for pi,p in enumerate(par):
        for idx in np.ndindex(p.shape):
            old=p[idx];eps=.001;p[idx]=old+eps;up=turn_grad(x,counts,phase,turn,y,weights,ids,*par)[0];p[idx]=old-eps;dn=turn_grad(x,counts,phase,turn,y,weights,ids,*par)[0];p[idx]=old
            assert abs((up-dn)/(2*eps)-g[pi][idx])<2e-5;checks+=1
    pred=turn_forward(x,counts,phase,turn,*par);mirror=turn_forward(x[:,::-1].copy(),counts[:,::-1].copy(),phase,-turn,*par);assert np.max(abs(pred+mirror))<1e-6
    oldout=par[2][:,:2].copy();anti=np.concatenate([oldout,-oldout],axis=1);a=forward(x,counts,phase,par[0],par[1],oldout,1);b=turn_forward(x,counts,phase,turn,par[0],par[1],anti);assert np.max(abs(a-b))<1e-6
    return dict(gradient_checks=checks,colour_and_turn_parity=True,antisymmetric_initialization_identity=True)
def fit(data,dev,par,seed,epochs,rate):
    rng=np.random.default_rng(seed);ids=np.random.default_rng(2026090603).permutation(len(data['y']))[:4000000];target=(data['y']-data['base'])/400
    par=[p.copy() for p in par];m=[np.zeros_like(p) for p in par];v=[np.zeros_like(p) for p in par];step=0;best=(float('inf'),0,None);curve=[];start=time.perf_counter()
    for epoch in range(1,epochs+1):
        rng.shuffle(ids)
        for at in range(0,len(ids),256):
            _,*g=turn_grad(data['x'],data['counts'],data['phase'],data['turn'],target,data['weights'],ids[at:at+256],*par);step+=1
            for j,p in enumerate(par):adam(p,g[j],m[j],v[j],step,rate,.02)
        pred=dev['base']+400*turn_forward(dev['x'],dev['counts'],dev['phase'],dev['turn'],*par);score=metrics(dev['y'],pred)['mae'];curve.append(dict(epoch=epoch,mae=score,seconds=time.perf_counter()-start));print('epoch',epoch,round(score,3),flush=True)
        if score<best[0]:best=(score,epoch,[p.copy() for p in par])
    par=best[2];pred=dev['base']+400*turn_forward(dev['x'],dev['counts'],dev['phase'],dev['turn'],*par);met={}
    for name,mask in [('all',np.ones(len(pred),bool)),('quiet',dev['quiet']),('guard',~dev['quiet']),('endgame',dev['phase']<=.25)]:met[name]=dict(model=metrics(dev['y'][mask],pred[mask]))
    return par,dict(width=par[0].shape[1],seed=seed,cap=len(ids),selected_epoch=best[1],metrics=met,curve=curve,seconds=time.perf_counter()-start),pred
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int,required=True);ap.add_argument('--cpu',type=int,required=True);a=ap.parse_args()
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(a.cpu)['applied'];dest=HERE/f'turn-aware/s{a.seed}';dest.mkdir(parents=True,exist_ok=False);checks=verify_turn();source=HERE/f'extended/s{a.seed}/public.npz';z=np.load(source);par=[z['w'],z['bias'],np.concatenate([z['out'],-z['out']],axis=1)]
    data={k:np.load(HERE/f'data-r2/{k}.npy',mmap_mode='r') for k in ('x','counts','phase','base','y','weights','quiet')};data['turn']=infer_turn(data['x'],data['counts'],data['phase'],data['base']);dev=dict(np.load(HERE/'data-r2/development.npz'));dev['turn']=infer_turn(dev['x'],dev['counts'],dev['phase'],dev['base'])
    cross=np.load(OLD/'public-data/transfer-piece.npz');tr=cross['split']==0;tt={k:cross[k][tr] for k in data if k!='turn'};td={k:cross[k][~tr] for k in data if k!='turn'}
    for d in (tt,td):d['turn']=infer_turn(d['x'],d['counts'],d['phase'],d['base'])
    with (dest/'results.jsonl').open('x') as f:
        def emit(r):f.write(json.dumps(r)+'\n');f.flush()
        emit(dict(type='metadata',checks=checks,script_sha256=sha(__file__),checkpoint_sha256=sha(source),rows=4000000,epochs=4,rate=.0003,scope='Turn-aware head continuation on same4m data. More optimization plus added expressive power; not a compute-matched architecture-strength proof. Exact colour+turn symmetry, no published model.'))
        par,r,_=fit(data,dev,par,a.seed,4,.0003);np.savez_compressed(dest/'public.npz',w=par[0],bias=par[1],out=par[2]);emit(dict(type='trial',**r))
        par,r,pred=fit(tt,td,par,a.seed,45,.001);np.savez_compressed(dest/'adapted.npz',w=par[0],bias=par[1],out=par[2],pred=pred);emit(dict(type='adaptation',**r));emit(dict(type='complete'))
if __name__=='__main__':main()
