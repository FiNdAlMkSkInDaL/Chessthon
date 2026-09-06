"""Separate unique-data scaling from the number of optimizer updates."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import json,time
import numpy as np
from train import HERE,OLD,fit,sha
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(2)['applied']
dest=HERE/'compute-control';dest.mkdir(exist_ok=False)
plan=dict(cap=125000,epochs=64,width=32,seeds=[260908,260909],training_examples=8000000,control='Compare1m x8epochs=8m examples; ceil batch boundaries give31296 versus31256 optimizer updates. Fresh random initialization, same nested rows,dev,targets andoptimizer. This separates eightfold unique-data volume from nearly equal training compute.',script_sha256=sha(__file__))
(dest/'plan.json').write_text(json.dumps(plan,indent=2))
data={k:np.load(HERE/f'data/{k}.npy',mmap_mode='r') for k in ('x','counts','phase','base','y','weights','quiet')};dev=dict(np.load(HERE/'data/development.npz'));cross=np.load(OLD/'public-data/transfer-piece.npz');tr=cross['split']==0
td={k:cross[k][~tr] for k in data};tt={k:cross[k][tr] for k in data}
with (dest/'results.jsonl').open('x') as f:
    def emit(r):f.write(json.dumps(r)+'\n');f.flush();print(json.dumps({k:v for k,v in r.items() if k!='curve'}),flush=True)
    emit(dict(type='metadata',**plan))
    for seed in plan['seeds']:
        par,r,_=fit(data,dev,125000,32,seed,64);np.savez_compressed(dest/f's{seed}-public.npz',w=par[0],bias=par[1],out=par[2]);emit(dict(type='trial',**r))
        pp,rr,pred=fit(tt,td,len(tt['y']),32,seed,45,par,.001);np.savez_compressed(dest/f's{seed}-adapted.npz',w=pp[0],bias=pp[1],out=pp[2],pred=pred);emit(dict(type='adaptation',**rr))
    emit(dict(type='complete'))
