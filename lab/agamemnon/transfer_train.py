"""Controlled original pretraining-transfer experiment on search-state labels.
Random-init versus public pretraining use identical fine-tuning budgets and base.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,json,time
import numpy as np
from representations import HERE,sha,forward,batch_grad,adam,metrics
from public_train import CONFIGS

def fit(config,lane,seed,initialization,dest):
    name,rep,mode,width=config;z=np.load(HERE/f'public-data/transfer-{rep}.npz');x,counts,phase,base,y,split,quiet,weights=[z[k] for k in ('x','counts','phase','base','y','split','quiet','weights')]
    tr=np.flatnonzero(split==0);va=split==1;rng=np.random.default_rng(seed);target=(y-base)/400
    if initialization=='public':
        checkpoint=HERE/f'public-screen/lane{lane}/{name}-100000-{seed}.npz';old=np.load(checkpoint);par=[old[k].copy() for k in ('w','bias','out')];source=sha(checkpoint)
    else:
        par=[rng.normal(0,.025,(768 if rep=='piece' else 3468,width)).astype(np.float32),np.full(width,.5 if mode==1 else 0,np.float32),rng.normal(0,.04,(width,2)).astype(np.float32)];source='original random initialization'
    m=[np.zeros_like(p) for p in par];v=[np.zeros_like(p) for p in par];step=0;best=(float('inf'),0,[p.copy() for p in par]);curve=[];start=time.perf_counter()
    initialpred=base+400*forward(x,counts,phase,*par,mode)
    for epoch in range(1,46):
        rng.shuffle(tr)
        for pos in range(0,len(tr),128):
            _,*grads=batch_grad(x,counts,phase,target,weights,tr[pos:pos+128],*par,mode);step+=1
            for j,p in enumerate(par):adam(p,grads[j],m[j],v[j],step,.001,.02)
        pred=base+400*forward(x,counts,phase,*par,mode);met=metrics(y[va],pred[va]);curve.append(dict(epoch=epoch,development_mae=met['mae'],train_mae=metrics(y[tr],pred[tr])['mae']))
        if met['mae']<best[0]:best=(met['mae'],epoch,[p.copy() for p in par])
    par=best[2];pred=base+400*forward(x,counts,phase,*par,mode)
    # Exact released static scores are already recorded on these same rows.
    control=np.load(HERE/'data/piece.npz')['base'];assert len(control)==len(base)
    result=dict(name=name,seed=seed,initialization=initialization,source=source,selected_epoch=best[1],seconds=time.perf_counter()-start,curve=curve,initial_development=metrics(y[va],initialpred[va]),metrics={})
    for label,mask in [('development',va),('quiet',va&quiet),('guard',va&~quiet),('endgame',va&(phase<=.25)),('high',va&(phase>=.75)),('train',split==0)]:result['metrics'][label]=dict(pesto=metrics(y[mask],base[mask]),tempest=metrics(y[mask],control[mask]),model=metrics(y[mask],pred[mask]))
    np.savez_compressed(dest/f'{name}-{initialization}-{seed}.npz',w=par[0],bias=par[1],out=par[2],pred=pred)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lane',type=int,required=True);ap.add_argument('--cpu',type=int,required=True);a=ap.parse_args()
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(a.cpu)['applied'];dest=HERE/f'transfer-screen/lane{a.lane}';dest.mkdir(parents=True,exist_ok=False);config=CONFIGS[a.lane];identity=sha(__file__)
    with (dest/'results.jsonl').open('x') as f:
        def emit(r):f.write(json.dumps(r)+'\n');f.flush()
        emit(dict(type='metadata',script_sha256=identity,kernels_sha256=sha(HERE/'representations.py'),data_sha256=sha(HERE/'public-data/manifest.json'),config=config,seeds=[260906,260907],epochs=45,scope='Reused family-disjoint search-state DEVELOPMENT. Public source lacks game IDs; no claim of cross-corpus family separation. Same base/optimizer/fine-tuning budget within each comparison.'))
        for seed in (260906,260907):
            for initialization in ('random','public'):
                result=fit(config,a.lane,seed,initialization,dest);emit(dict(type='trial',**result));print(config[0],initialization,seed,round(result['metrics']['development']['model']['mae'],2),round(result['seconds'],1),flush=True)
        assert identity==sha(__file__);emit(dict(type='complete'))
if __name__=='__main__':main()
