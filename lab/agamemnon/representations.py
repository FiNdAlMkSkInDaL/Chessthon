"""Original sparse value models; research only, not a submission/engine port.

Shared colour-relative features and antisymmetric outputs enforce colour parity.
The FM arm stores sums and sums of squares; the NN arm stores linear sums.
All optimization is our own bounded single-thread NumPy/Numba implementation.
"""
import os
for _k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS'):
    os.environ[_k]='1'
import argparse, collections, hashlib, json, sys, time
from pathlib import Path
import chess
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def encode(board, representation):
    rows=[]
    for color in (True,False):
        flip=0 if color else 56
        king=board.king(color)^flip
        bucket=(king%8)//2+4*(king//8>=4)
        row=[]
        for sq,p in board.piece_map().items():
            sq=sq^flip; typ=p.piece_type-1+(0 if p.color==color else 6)
            row.append(typ*64+sq)
            if representation=='bucket': row.append(768+bucket*768+typ*64+sq)
            elif representation=='relative':
                dx=sq%8-king%8+7;dy=sq//8-king//8+7
                row.append(768+typ*225+dy*15+dx)
        rows.append(sorted(row))
    return rows

@njit
def forward(x, counts, phase, w, bias, out, mode):
    n=len(x); h=w.shape[1]; p=np.zeros(n,np.float32)
    for i in range(n):
        for side in range(2):
            sign=1.0 if side==0 else -1.0
            for j in range(h):
                a=bias[j];sq=0.0
                for k in range(counts[i,side]):
                    v=w[x[i,side,k],j];a+=v;sq+=v*v
                if mode==0: z=a
                elif mode==1: z=min(2.0,max(0.0,a))
                else: z=.5*((a-bias[j])**2-sq)
                o=phase[i]*out[j,0]+(1-phase[i])*out[j,1]
                p[i]+=sign*z*o
    return p

@njit
def batch_grad(x,counts,phase,y,weights,ids,w,bias,out,mode):
    gw=np.zeros_like(w);gb=np.zeros_like(bias);go=np.zeros_like(out)
    h=w.shape[1];loss=0.0;total=0.0
    sums=np.empty((2,h),np.float32);zs=np.empty((2,h),np.float32)
    for i in ids: total+=weights[i]
    for i in ids:
        pred=0.0
        for side in range(2):
            sign=1.0 if side==0 else -1.0
            for j in range(h):
                a=bias[j];sq=0.0
                for k in range(counts[i,side]):
                    v=w[x[i,side,k],j];a+=v;sq+=v*v
                sums[side,j]=a
                z=a if mode==0 else (min(2.0,max(0.0,a)) if mode==1 else .5*((a-bias[j])**2-sq))
                zs[side,j]=z
                pred+=sign*z*(phase[i]*out[j,0]+(1-phase[i])*out[j,1])
        err=pred-y[i];wt=weights[i]/total
        loss+=wt*(.5*err*err if abs(err)<=1 else abs(err)-.5)
        d=min(1.0,max(-1.0,err))*wt
        for side in range(2):
            sign=1.0 if side==0 else -1.0
            for j in range(h):
                a=sums[side,j];dz=d*sign*(phase[i]*out[j,0]+(1-phase[i])*out[j,1])
                go[j,0]+=d*sign*zs[side,j]*phase[i]
                go[j,1]+=d*sign*zs[side,j]*(1-phase[i])
                if mode==1 and (a<=0 or a>=2): dz=0.0
                if mode!=2: gb[j]+=dz
                for k in range(counts[i,side]):
                    idx=x[i,side,k]
                    gw[idx,j]+=dz*(a-bias[j]-w[idx,j] if mode==2 else 1.0)
    return loss,gw,gb,go

@njit
def adam(p,g,m,v,step,rate,decay):
    pp=p.reshape(-1);gg=g.reshape(-1);mm=m.reshape(-1);vv=v.reshape(-1)
    for j in range(len(pp)):
        q=gg[j];mm[j]=.9*mm[j]+.1*q;vv[j]=.999*vv[j]+.001*q*q
        pp[j]-=rate*((mm[j]/(1-.9**step))/(np.sqrt(vv[j]/(1-.999**step))+1e-8)+decay*pp[j])

def load_data():
    states={r['id']:r for r in map(json.loads,(ROOT/'lab/tempest_build/data/states.jsonl').read_text().splitlines())}
    labels={}
    paths=sorted((ROOT/'lab/tempest_build/data').glob('labels-?.jsonl'))
    for p in paths:
        data=list(map(json.loads,p.read_text().splitlines()));assert data[-1]['type']=='complete'
        for r in data:
            if r['type']=='label': labels[r['id']]=r['reference']
    rows=[r for k,r in states.items() if labels[k].get('white_mate') is None and 'terminal' not in labels[k] and abs(labels[k]['white_cp'])<2000]
    return rows,labels,paths

def prepare():
    dest=HERE/'data';dest.mkdir(exist_ok=False)
    rows,labels,paths=load_data();boards=[chess.Board(r['fen']) for r in rows]
    split=np.array([0 if r['split']=='train' else 1 for r in rows],np.int8)
    # Prior test and validation have both been inspected; explicitly pool as development.
    trfam={r['family'] for r in rows if r['split']=='train'}
    vafam={r['family'] for r in rows if r['split']!='train'}
    assert not trfam&vafam
    familyrank={f:i/len(trfam) for i,f in enumerate(sorted(trfam,key=lambda f:hashlib.sha256(('agamemnon-scale-v1'+f).encode()).hexdigest()))}
    ranks=np.array([familyrank.get(r['family'],1) for r in rows],np.float32)
    phase=np.array([min(24,sum(len(b.pieces(pt,c))*v for pt,v in [(2,1),(3,1),(4,2),(5,4)] for c in (True,False)))/24 for b in boards],np.float32)
    base=np.array([r['static_white_cp'] for r in rows],np.float32)
    y=np.array([labels[r['id']]['white_cp'] for r in rows],np.float32)
    quiet=np.array([r['kind']=='quiet' for r in rows])
    roots=collections.Counter(r['root_id'] for r in rows)
    weights=np.array([(1 if r['kind']=='quiet' else .25)/roots[r['root_id']] for r in rows],np.float32)
    for rep in ('piece','bucket','relative'):
        encoded=[encode(b,rep) for b in boards];maxn=max(len(z) for pair in encoded for z in pair)
        counts=np.array([[len(z) for z in pair] for pair in encoded],np.int32)
        x=np.zeros((len(rows),2,maxn),np.int32)
        for i,pair in enumerate(encoded):
            for side,z in enumerate(pair): x[i,side,:len(z)]=z
        for b in boards[:150]:assert encode(b.mirror(),rep)==encode(b,rep)[::-1]
        np.savez_compressed(dest/f'{rep}.npz',x=x,counts=counts,phase=phase,base=base,y=y,split=split,ranks=ranks,quiet=quiet,weights=weights)
    (dest/'rows.jsonl').write_text(''.join(json.dumps({k:r[k] for k in ('id','fen','family','root_id','kind','split')})+'\n' for r in rows))
    meta=dict(n=len(rows),train=int(sum(split==0)),development=int(sum(split==1)),train_families=len(trfam),development_families=len(vafam),quiet=int(quiet.sum()),endgame=int(sum(phase<=.25)),scope='Reused family-disjoint DEVELOPMENT split, not independent holdout; same original Tempest static base in every arm; no residual output clipping.',sources={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'lab/tempest_build/data/states.jsonl',*paths]},encoder_sha256=sha(__file__))
    (dest/'manifest.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta),flush=True)

def metrics(y,p):
    err=np.abs(y-p)
    return dict(n=len(y),mae=float(np.mean(err)),rmse=float(np.sqrt(np.mean(err**2))),p90=float(np.quantile(err,.9))) if len(y) else None

def verify():
    rng=np.random.default_rng(67);x=np.array([[[0,1,2],[2,3,4]],[[0,3,4],[1,2,4]]],np.int32)
    counts=np.full((2,2),3,np.int32);phase=np.array([.4,.8],np.float32);y=np.array([.1,-.2],np.float32);weights=np.ones(2,np.float32);ids=np.arange(2)
    checks=0
    for mode in range(3):
        par=[rng.normal(0,.04,(5,4)).astype(np.float32),np.full(4,.5,np.float32),rng.normal(0,.1,(4,2)).astype(np.float32)]
        loss,*grads=batch_grad(x,counts,phase,y,weights,ids,*par,mode)
        for pi,p in enumerate(par):
            for idx in list(np.ndindex(p.shape))[:12]:
                old=p[idx];eps=.001;p[idx]=old+eps;up=batch_grad(x,counts,phase,y,weights,ids,*par,mode)[0]
                p[idx]=old-eps;dn=batch_grad(x,counts,phase,y,weights,ids,*par,mode)[0];p[idx]=old
                assert abs((up-dn)/(2*eps)-grads[pi][idx])<2e-5,(mode,pi,idx)
                checks+=1
        pred=forward(x,counts,phase,*par,mode);mirror=forward(x[:,::-1].copy(),counts[:,::-1].copy(),phase,*par,mode)
        assert np.max(np.abs(pred+mirror))<1e-6
    return dict(gradient_checks=checks,colour_parity_modes=3)

CONFIGS=[('additive','piece',0,1),('acc32','piece',1,32),('acc128','piece',1,128),('acc256','piece',1,256),('bucket32','bucket',1,32),('bucket128','bucket',1,128),('relative32','relative',1,32),('relative128','relative',1,128),('pair32','piece',2,32),('pair128','piece',2,128)]

def fit(config,fraction,seed,epochs=45):
    name,rep,mode,width=config;data=np.load(HERE/f'data/{rep}.npz')
    x,counts,phase,base,y,split,ranks,quiet,weights=[data[k] for k in ('x','counts','phase','base','y','split','ranks','quiet','weights')]
    tr=np.flatnonzero((split==0)&(ranks<fraction));va=split==1
    rng=np.random.default_rng(seed);features={'piece':768,'bucket':6912,'relative':3468}[rep]
    w=rng.normal(0,.025,(features,width)).astype(np.float32);bias=np.full(width,.5 if mode==1 else 0,np.float32)
    out=rng.normal(0,.04,(width,2)).astype(np.float32)
    if mode==0:w[:]=0;out[:]=1
    par=[w,bias,out];m=[np.zeros_like(p) for p in par];v=[np.zeros_like(p) for p in par]
    target=(y-base)/400;step=0;curve=[];best=(float('inf'),0,None);start=time.perf_counter()
    for epoch in range(1,epochs+1):
        rng.shuffle(tr)
        for pos in range(0,len(tr),128):
            _,*grads=batch_grad(x,counts,phase,target,weights,tr[pos:pos+128],*par,mode);step+=1
            for j,p in enumerate(par):
                if mode==0 and j>0:continue
                adam(p,grads[j],m[j],v[j],step,.002,.02)
        pred=base+400*forward(x,counts,phase,*par,mode)
        score=metrics(y[va],pred[va])['mae'];curve.append(dict(epoch=epoch,train_mae=metrics(y[tr],pred[tr])['mae'],development_mae=score))
        if score<best[0]:best=(score,epoch,[p.copy() for p in par])
    pred=base+400*forward(x,counts,phase,*best[2],mode)
    result=dict(name=name,representation=rep,mode=mode,width=width,seed=seed,fraction=fraction,train_n=len(tr),selected_epoch=best[1],seconds=time.perf_counter()-start,parameters=sum(p.size for p in par),float32_bytes=sum(p.nbytes for p in par),metrics={},curve=curve)
    for key,mask in [('development',va),('quiet',va&quiet),('guard',va&~quiet),('endgame',va&(phase<=.25)),('high',va&(phase>=.75)),('train',(split==0)&(ranks<fraction))]:
        result['metrics'][key]=dict(base=metrics(y[mask],base[mask]),model=metrics(y[mask],pred[mask]))
    return result,best[2],pred

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--lane',type=int,default=0);ap.add_argument('--lanes',type=int,default=4);ap.add_argument('--cpu',type=int,default=2);a=ap.parse_args()
    if os.name=='nt':
        from lab.laptop_runner import apply_windows_affinity
        assert apply_windows_affinity(a.cpu)['applied']
    else:os.sched_setaffinity(0,{a.cpu})
    if a.prepare:prepare();return
    dest=HERE/f'screen/lane{a.lane}';dest.mkdir(parents=True,exist_ok=False)
    checks=verify();configs=CONFIGS[a.lane::a.lanes];identity=sha(__file__)
    with (dest/'results.jsonl').open('x') as f:
        def emit(r):f.write(json.dumps(r)+'\n');f.flush()
        emit(dict(type='metadata',checks=checks,script_sha256=identity,data_sha256=sha(HERE/'data/manifest.json'),configs=configs,epochs=45,fractions=[.25,.5,1],seeds=[260906,260907]))
        for config in configs:
            for fraction in (.25,.5,1):
                for seed in (260906,260907):
                    r,par,pred=fit(config,fraction,seed);tag=f'{config[0]}-{fraction}-{seed}'
                    np.savez_compressed(dest/f'{tag}.npz',w=par[0],bias=par[1],out=par[2],pred=pred)
                    emit(dict(type='trial',**r));print(tag,round(r['metrics']['development']['model']['mae'],2),round(r['seconds'],1),flush=True)
        assert identity==sha(__file__);emit(dict(type='complete'))
if __name__=='__main__':main()
