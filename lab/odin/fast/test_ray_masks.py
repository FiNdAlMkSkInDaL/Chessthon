"""Exhaustive relevant rook/bishop occupancies plus full-width random blockers."""
import os,sys,argparse,json,hashlib,random,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ROOT/'odin_ray_core');ap.add_argument('--cpu',type=int,default=8);ap.add_argument('--output',type=Path,default=ROOT/'lab/odin/fast/ray-mask-test.json');args=ap.parse_args()
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
sys.path.insert(0,str(ROOT))
if os.name=='nt':
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(args.cpu)['applied']
else:os.sched_setaffinity(0,{args.cpu})
sys.path.insert(0,str(args.source.resolve()))
import numpy as np,core_nb as c
from numba import njit

@njit(cache=False)
def reference(sq,occ,dirs):
    attacks=np.uint64(0)
    for i in range(len(dirs)):
        d=dirs[i];f=(sq&7)+c.RAY_DF[d];r=(sq>>3)+c.RAY_DR[d]
        while 0<=f<8 and 0<=r<8:
            b=c.bit(r*8+f);attacks|=b
            if occ&b:break
            f+=c.RAY_DF[d];r+=c.RAY_DR[d]
    return attacks

@njit(cache=False)
def exhaustive():
    count=0
    for sq in range(64):
        for kind in range(2):
            dirs=c.ROOK_DI if kind==0 else c.BISHOP_DI
            mask=reference(sq,np.uint64(0),dirs)
            # Include edge blockers too, proving the entire ray occupancy space.
            sub=np.uint64(0)
            while True:
                assert c.sliding(sq,sub,dirs)==reference(sq,sub,dirs)
                count+=1
                sub=(sub-mask)&mask
                if sub==0:break
    return count

began=time.monotonic();count=exhaustive();rng=random.Random(20260906)
for i in range(10000):
    occ=np.uint64(rng.getrandbits(64));sq=rng.randrange(64)
    for dirs in (c.ROOK_DI,c.BISHOP_DI):assert c.sliding(sq,occ,dirs)==reference(sq,occ,dirs)
    assert c.msb(occ)==int(occ).bit_length()-1
assert c.msb(np.uint64(0))==0
for i in range(64):
    for j in range(64):assert c.msb(np.uint64((1<<i)|(1<<j)))==max(i,j)
result={'pass':True,'exhaustive_occupancies':int(count),'random_full_width':20000,'msb_single_two_bit':4096,'seconds':time.monotonic()-began,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.source.glob('*.py')}}
args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='source_hashes'}),flush=True)
