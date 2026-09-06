"""Original model/data scaling on a bounded permitted public data slice.
No published weights; models initialize randomly and use our own training kernels.
Validation is public-block development, transfer is reused Tempest development.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,json,time
import numpy as np
from representations import HERE,sha,forward,batch_grad,adam,metrics,verify
CONFIGS=[('public-acc32','piece',1,32),('public-acc128','piece',1,128),('public-pair32','piece',2,32),('public-relative32','relative',1,32)]

def run(config,cap,seed,dest):
    name,rep,mode,width=config;z=np.load(HERE/f'public-data/public-{rep}.npz');cross=np.load(HERE/f'public-data/transfer-{rep}.npz')
    x,counts,phase,base,y,split,quiet,weights=[z[k] for k in ('x','counts','phase','base','y','split','quiet','weights')]
    tr=np.flatnonzero(split==0)[:cap];va=split==1;rng=np.random.default_rng(seed);target=(y-base)/400
    par=[rng.normal(0,.025,(768 if rep=='piece' else 3468,width)).astype(np.float32),np.full(width,.5 if mode==1 else 0,np.float32),rng.normal(0,.04,(width,2)).astype(np.float32)]
    m=[np.zeros_like(p) for p in par];v=[np.zeros_like(p) for p in par];step=0;best=(float('inf'),0,None);curve=[];start=time.perf_counter()
    # The training horizon is fixed for every arm; larger data gets more updates.
    for epoch in range(1,13):
        rng.shuffle(tr)
        for pos in range(0,len(tr),256):
            _,*grads=batch_grad(x,counts,phase,target,weights,tr[pos:pos+256],*par,mode);step+=1
            for j,p in enumerate(par):adam(p,grads[j],m[j],v[j],step,.002,.02)
        pred=base[va]+400*forward(x[va],counts[va],phase[va],*par,mode)
        met=metrics(y[va],pred);trainpred=base[tr[:2048]]+400*forward(x[tr[:2048]],counts[tr[:2048]],phase[tr[:2048]],*par,mode)
        curve.append(dict(epoch=epoch,development_mae=met['mae'],sampled_train_mae=metrics(y[tr[:2048]],trainpred)['mae']))
        if met['mae']<best[0]:best=(met['mae'],epoch,[p.copy() for p in par])
    par=best[2];pred=base+400*forward(x,counts,phase,*par,mode)
    cpred=cross['base']+400*forward(cross['x'],cross['counts'],cross['phase'],*par,mode)
    result=dict(name=name,seed=seed,cap=cap,train_n=len(tr),epochs=12,selected_epoch=best[1],seconds=time.perf_counter()-start,parameters=sum(p.size for p in par),curve=curve,metrics={})
    for label,mask in [('development',va),('quiet',va&quiet),('guard',va&~quiet),('endgame',va&(phase<=.25)),('high',va&(phase>=.75)),('train_sample',np.isin(np.arange(len(x)),tr[:2048]))]:result['metrics'][label]=dict(pesto=metrics(y[mask],base[mask]),model=metrics(y[mask],pred[mask]))
    # Existing Tempest labels are finite SF19 references. Public labels are SF16:
    # transfer measures distribution + calibration differences, not pure strength.
    mask=cross['split']==1;result['transfer']=dict(pesto=metrics(cross['y'][mask],cross['base'][mask]),model=metrics(cross['y'][mask],cpred[mask]))
    result['scope']='Original scratch model, PeSTO residual without output clipping. Public block split lacks game IDs. Transfer diagnostic not independent strength validation.'
    tag=f'{name}-{cap}-{seed}';np.savez_compressed(dest/f'{tag}.npz',w=par[0],bias=par[1],out=par[2],transfer_pred=cpred)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lane',type=int,required=True);ap.add_argument('--cpu',type=int,required=True);a=ap.parse_args()
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(a.cpu)['applied'];dest=HERE/f'public-screen/lane{a.lane}';dest.mkdir(parents=True,exist_ok=False);identity=sha(__file__)
    config=CONFIGS[a.lane]
    with (dest/'results.jsonl').open('x') as f:
        def emit(r):f.write(json.dumps(r)+'\n');f.flush()
        emit(dict(type='metadata',script_sha256=identity,kernels_sha256=sha(HERE/'representations.py'),data_sha256=sha(HERE/'public-data/manifest.json'),config=config,checks=verify(),caps=[8000,32000,100000],seeds=[260906,260907],epochs=12))
        for cap in (8000,32000,100000):
            for seed in (260906,260907):
                result=run(config,cap,seed,dest);emit(dict(type='trial',**result));print(config[0],cap,seed,round(result['metrics']['development']['model']['mae'],2),round(result['transfer']['model']['mae'],2),round(result['seconds'],1),flush=True)
        assert sha(__file__)==identity;emit(dict(type='complete'))
if __name__=='__main__':main()
