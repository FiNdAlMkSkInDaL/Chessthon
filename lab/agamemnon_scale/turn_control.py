"""Same-data, same-update control for the turn-aware head experiment."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,json
import numpy as np
from train import HERE,OLD,fit,sha
from lab.laptop_runner import apply_windows_affinity
ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int,required=True);ap.add_argument('--cpu',type=int,required=True);a=ap.parse_args();assert apply_windows_affinity(a.cpu)['applied']
dest=HERE/f'turn-control/s{a.seed}';dest.mkdir(parents=True,exist_ok=False);source=HERE/f'extended/s{a.seed}/public.npz';z=np.load(source);par=[z[k] for k in ('w','bias','out')]
data={k:np.load(HERE/f'data-r2/{k}.npy',mmap_mode='r') for k in ('x','counts','phase','base','y','weights','quiet')};dev=dict(np.load(HERE/'data-r2/development.npz'));cross=np.load(OLD/'public-data/transfer-piece.npz');tr=cross['split']==0;tt={k:cross[k][tr] for k in data};td={k:cross[k][~tr] for k in data}
with (dest/'results.jsonl').open('x') as f:
    def emit(r):f.write(json.dumps(r)+'\n');f.flush();print(r['type'],r.get('selected_epoch'),r.get('metrics',{}).get('all',{}),flush=True)
    emit(dict(type='metadata',script_sha256=sha(__file__),checkpoint_sha256=sha(source),rows=4000000,epochs=4,rate=.0003,scope='Retain antisymmetric head, same starting function/data/update count/rate/seed as turn-aware arm. No independent strength claim.'))
    par,r,_=fit(data,dev,4000000,32,a.seed,4,par,.0003);np.savez_compressed(dest/'public.npz',w=par[0],bias=par[1],out=par[2]);emit(dict(type='trial',**r))
    par,r,pred=fit(tt,td,len(tt['y']),32,a.seed,45,par,.001);np.savez_compressed(dest/'adapted.npz',w=par[0],bias=par[1],out=par[2],pred=pred);emit(dict(type='adaptation',**r));emit(dict(type='complete'))
