"""Resumable bounded public acquisition and parallel, once-only feature cache."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'): os.environ[k]='1'
import concurrent.futures as cf, hashlib,json,math,sys,time
from pathlib import Path
import numpy as np,chess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'lab/agamemnon'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OLD))
from chessbench_slice import fetch,decode
from public_data_prepare import key,phase,pesto
from representations import encode,sha
def canonical(b):return hashlib.sha256(min(key(b),key(b.mirror())).encode()).digest()[:16]
def block(i):
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(2+i%4)['applied']
    dest=HERE/'data';plan=json.loads((dest/'plan.json').read_text());start=plan['starts'][i]
    out=dest/f'block-{i:03d}.npz';meta=dest/f'block-{i:03d}.json'
    if out.exists() and meta.exists():
        r=json.loads(meta.read_text());assert sha(out)==r['array_sha256'];return r
    started=time.perf_counter();raw=dest/f'raw-{i:03d}.bin';off=dest/f'offsets-{i:03d}.bin'
    for attempt in range(4):
        try:
            if not off.exists():off.write_bytes(fetch(plan['index_start']+8*(start-1),plan['index_start']+8*(start+10000)-1,plan['etag'])[0])
            limits=off.read_bytes();offsets=np.frombuffer(limits,dtype='<u8');assert len(offsets)==10001 and np.all(offsets[1:]>offsets[:-1])
            if not raw.exists():raw.write_bytes(fetch(int(offsets[0]),int(offsets[-1])-1,plan['etag'])[0])
            blob=raw.read_bytes();assert len(blob)==int(offsets[-1]-offsets[0]);break
        except Exception:
            if attempt==3:raise
            time.sleep(1+attempt)
    rows=[];origin=int(offsets[0])
    for j in range(10000):
        fen,p=decode(blob[int(offsets[j])-origin:int(offsets[j+1])-origin])
        if not .001<p<.999:continue
        b=chess.Board(fen)
        if b.halfmove_clock>=80 or b.ply()>=500 or b.is_game_over():continue
        assert b.is_valid()
        ph=phase(b);q=not b.is_check() and not any(b.is_capture(m) or m.promotion for m in b.legal_moves)
        rows.append((fen,canonical(b),encode(b,'piece'),ph,pesto(b,ph),math.log(p/(1-p))/.00368208*(1 if b.turn else -1),q,start+j))
    n=len(rows);x=np.zeros((n,2,32),np.int32);counts=np.zeros((n,2),np.int32)
    for j,r in enumerate(rows):
        for side,ids in enumerate(r[2]):x[j,side,:len(ids)]=ids;counts[j,side]=len(ids)
    np.savez_compressed(out,x=x,counts=counts,phase=np.array([r[3] for r in rows],np.float32),base=np.array([r[4] for r in rows],np.float32),y=np.array([r[5] for r in rows],np.float32),quiet=np.array([r[6] for r in rows]),keys=np.array([r[1] for r in rows],dtype='V16'),records=np.array([r[7] for r in rows],np.int64))
    # Small, deterministic policy roots; complete value training data stays numeric.
    (dest/f'roots-{i:03d}.json').write_text(json.dumps([dict(fen=r[0],key=r[1].hex(),record=r[7]) for r in rows[:8]]))
    r=dict(block=i,first_record=start,rows=n,seconds=time.perf_counter()-started,raw_sha256=sha(raw),offset_sha256=sha(off),array_sha256=sha(out))
    meta.write_text(json.dumps(r));return r
def main():
    dest=HERE/'data';dest.mkdir(exist_ok=True);prior=json.loads((OLD/'chessbench/plan.json').read_text())
    if not (dest/'plan.json').exists():
        rng=np.random.default_rng(2026090602);starts=[]
        while len(starts)<112:
            n=int(rng.integers(1,prior['records']-10000))
            if all(abs(n-s)>20000 for s in starts+prior['starts']):starts.append(n)
        plan={k:prior[k] for k in ('url','etag','generation','index_start','attribution','source')};plan.update(starts=starts,excluded_starts=prior['starts'],records_per_block=10000,seed=2026090602,script_sha256=sha(__file__))
        (dest/'plan.json').write_text(json.dumps(plan,indent=2))
    started=time.perf_counter()
    with cf.ProcessPoolExecutor(max_workers=4) as pool:
        reports=[]
        for r in pool.map(block,range(112)):
            reports.append(r);print(json.dumps(r),flush=True)
    dev=np.load(OLD/'public-data/public-piece.npz');mask=dev['split']==1
    np.savez_compressed(dest/'development.npz',**{k:dev[k][mask] for k in ('x','counts','phase','base','y','quiet','weights')})
    forbidden=set()
    for file in (OLD/'public-data/rows.jsonl',OLD/'data/rows.jsonl'):
        for line in file.open():
            r=json.loads(line)
            if file.name=='rows.jsonl' and file.parent.name=='public-data' and r['split']==0:continue
            forbidden.add(canonical(chess.Board(r['fen'])))
    seen=set(forbidden);keep=[];removed=0
    for i in range(112):
        z=np.load(dest/f'block-{i:03d}.npz');idx=[]
        for j,k in enumerate(z['keys']):
            b=k.tobytes()
            if b in seen:removed+=1;continue
            seen.add(b);idx.append(j)
        keep.append(np.array(idx,np.int64))
    n=sum(map(len,keep));assert n>=1000000,n
    shapes=dict(x=((2,32),np.int32),counts=((2,),np.int32),phase=((),np.float32),base=((),np.float32),y=((),np.float32),weights=((),np.float32),quiet=((),bool))
    arrays={k:np.lib.format.open_memmap(dest/f'{k}.npy',mode='w+',dtype=dtype,shape=(n,*tail)) for k,(tail,dtype) in shapes.items()}
    at=0
    for i,idx in enumerate(keep):
        z=np.load(dest/f'block-{i:03d}.npz');end=at+len(idx)
        for k in arrays:arrays[k][at:end]=np.where(z['quiet'][idx],1.,.25) if k=='weights' else z[k][idx]
        at=end
    for arr in arrays.values():arr.flush()
    report=dict(rows=n,development_rows=int(mask.sum()),removed_duplicates_or_development=removed,blocks=reports,seconds=time.perf_counter()-started,script_sha256=sha(__file__),plan_sha256=sha(dest/'plan.json'),arrays={k:sha(dest/f'{k}.npy') for k in arrays},scope='Training-only public records; exact/mirror development separation, game identities unavailable. Sealed records untouched. Memory-mapped cache shared by all training workers.')
    (dest/'manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('blocks','arrays')}),flush=True)
if __name__=='__main__':main()
