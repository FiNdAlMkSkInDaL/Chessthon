"""Continue original pretraining on expanded unique data, then adapt to search."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,json,time
import numpy as np
from train import HERE,OLD,fit,sha,check_kernel
from lab.laptop_runner import apply_windows_affinity
ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int,required=True);ap.add_argument('--cpu',type=int,required=True);a=ap.parse_args()
assert a.seed in (260908,260909) and apply_windows_affinity(a.cpu)['applied']
dest=HERE/f'extended/s{a.seed}';dest.mkdir(parents=True,exist_ok=False)
plan=dict(rows=4000000,epochs=8,width=32,seed=a.seed,rate=.0007,adapt_rate=.001,adapt_epochs=45,scope='Continue from original1m public checkpoint with fresh Adam moments; not bit-exact optimizer resumption.32m additional training examples from4m unique rows. Same development set, no holdout consumption. Best public checkpoint selected before search-state adaptation.',data_sha256=sha(HERE/'data-r2/manifest.json'),script_sha256=sha(__file__))
(dest/'plan.json').write_text(json.dumps(plan,indent=2))
data={k:np.load(HERE/f'data-r2/{k}.npy',mmap_mode='r') for k in ('x','counts','phase','base','y','weights','quiet')};assert len(data['y'])>=4000000;dev=dict(np.load(HERE/'data-r2/development.npz'))
source=HERE/f'train/lane1/w32-n1000000-s{a.seed}-public.npz';z=np.load(source);par=[z[k] for k in ('w','bias','out')]
cross=np.load(OLD/'public-data/transfer-piece.npz');tr=cross['split']==0;tt={k:cross[k][tr] for k in data};td={k:cross[k][~tr] for k in data}
with (dest/'results.jsonl').open('x') as f:
    def emit(r):f.write(json.dumps(r)+'\n');f.flush();print(json.dumps({k:v for k,v in r.items() if k!='curve'}),flush=True)
    emit(dict(type='metadata',**plan,checkpoint_sha256=sha(source)))
    par,r,_=fit(data,dev,4000000,32,a.seed,8,par,.0007);np.savez_compressed(dest/'public.npz',w=par[0],bias=par[1],out=par[2]);emit(dict(type='trial',**r))
    pp,rr,pred=fit(tt,td,len(tt['y']),32,a.seed,45,par,.001);np.savez_compressed(dest/'adapted.npz',w=pp[0],bias=pp[1],out=pp[2],pred=pred);emit(dict(type='adaptation',**rr))
    emit(dict(type='complete'))
