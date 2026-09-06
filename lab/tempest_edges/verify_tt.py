"""Native bucket collisions, flags, mate distances, keys, and age wrap."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(4)['applied']
source=HERE/'prototypes/bucket';sys.path.insert(0,str(source));t=time.perf_counter()
import agent,core_nb as c
cold=time.perf_counter()-t;assert c.NUMBA_READY
arr=(c.TT_KEY,c.TT_MOVE,c.TT_SCORE,c.TT_DEPTH,c.TT_GEN)
def clear(age=1):
    for a in arr:a.fill(0)
    c.TT_AGE[0]=age
def put(key,move=42,depth=8,flag=0,score=73,ply=0):c.tt_store(np.uint64(key),np.int32(move),np.int32(depth),np.int32(flag),np.int32(score),np.int32(ply),*arr,c.TT_AGE)
def get(key,ply=0):return c.tt_probe(np.uint64(key),np.int32(ply),*arr)
keys=[0x12340+i*c.TT_SIZE for i in range(4)]
clear();put(0);assert not get(0)[0] and not c.TT_KEY.any()
put(keys[0],depth=20);put(keys[1],depth=4);assert get(keys[0])[0] and get(keys[1])[0]
put(keys[2],depth=3);assert get(keys[0])[0] and not get(keys[1])[0] and get(keys[2])[0]
assert not get(keys[3])[0]  # full keys, not merely bucket identity
put(keys[0],move=99,depth=2,score=-100);assert get(keys[0])[1:]==(42,20,0,73)
put(keys[0],move=0,depth=21,score=88);assert get(keys[0])[1:]==(42,21,0,88)
checks=8
for flag in (c.EXACT,c.LOWER,c.UPPER):
    for score in (0,321,-543,c.MATE-10,-c.MATE+10):
        clear();put(keys[0],flag=flag,score=score,ply=3)
        assert get(keys[0],3)==(True,42,8,flag,score)
        expected=score-4 if score>=c.MATE_WIN else score+4 if score<=-c.MATE_WIN else score
        assert get(keys[0],7)[4]==expected;checks+=2
for age in range(1,64):
    previous=63 if age==1 else age-1
    clear(previous);put(keys[0],depth=20);c.TT_AGE[0]=age;put(keys[1],depth=10)
    put(keys[2],depth=5)
    # A one-generation-old depth-20 exact result beats current depth-10.
    assert get(keys[0])[0] and not get(keys[1])[0] and get(keys[2])[0]
    checks+=1
clear(53);put(keys[0],depth=30);c.TT_AGE[0]=1;put(keys[1],depth=4);put(keys[2],depth=5)
assert not get(keys[0])[0] and get(keys[1])[0] and get(keys[2])[0];checks+=1
clear();key=np.uint64(99119911);near=c.cap_tt_key(key,2);far=c.cap_tt_key(key,3)
assert near!=far;put(near);assert get(near)[0] and not get(far)[0];checks+=1
assert c.is_repeat(key,np.array([3,key,9],np.uint64),3)
assert not c.is_repeat(key,np.array([3,8,9],np.uint64),3);checks+=2
from lab.perft import POSITIONS
from board_nb import from_fen
for name,fen,expected in POSITIONS:assert c.perft_pos(from_fen(fen),3)==expected[3]
result=dict(audit='PASS',tt_checks=checks,perft_positions=6,cold_seconds=cold,source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file() and p.suffix in ('.py','.npz')},script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(HERE/'bucket-native.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='source_hashes'}))
