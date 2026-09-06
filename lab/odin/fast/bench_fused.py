"""Exact evaluation equivalence and paired hot-kernel throughput, offline only."""
import os,sys,json,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity,apply_windows_memory_job
assert apply_windows_affinity(8)['applied'];assert apply_windows_memory_job(2*1024**3)['applied']
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
sys.path.insert(0,str(ROOT/'odin_fused'));began=time.perf_counter()
import agent,core_nb as c,numpy as np,chess
from numba import njit
from board_nb import from_fen
assert c.NUMBA_READY;cold=time.perf_counter()-began
@njit
def reference(bb,st):
    f=c.positional_features_nb(bb,st);mg=0;eg=0
    for i in range(24):mg+=f[i]*c.FEATURE_MG[i];eg+=f[i]*c.FEATURE_EG[i]
    phase=min(24,np.int64(st[c.PHASE_ACC]));score=int(np.rint((mg*phase+eg*(24-phase))/24.0))
    return max(-400,min(400,score))
@njit
def loop(bbs,sts,n,which):
    total=0
    for _ in range(n):
        for i in range(len(bbs)):
            total+=c.positional_correction_nb(bbs[i],sts[i]) if which else reference(bbs[i],sts[i])
    return total
fens=[]
for p in (ROOT/'lab/odin/new_games').glob('round-*-screen.jsonl'):
    for line in p.read_text(encoding='utf-8').splitlines():
        r=json.loads(line)
        if r.get('type')=='position':fens.append(r['fen'])
for p in (ROOT/'lab/odin/fast/generation-openings').glob('*.fen'):fens.extend(p.read_text().splitlines())
fens=list(dict.fromkeys(fens));packs=[c.pack_pos(from_fen(fen)) for fen in fens]
bbs=np.array([p[0] for p in packs]);sts=np.array([p[2] for p in packs])
for bb,_,st in packs:assert int(c.positional_correction_nb(bb,st))==int(reference(bb,st))
assert loop(bbs,sts,1,True)==loop(bbs,sts,1,False)
timings=[]
for rep in range(6):
    values={}
    for which in ((True,False) if rep%2==0 else (False,True)):
        began=time.perf_counter();value=loop(bbs,sts,250,which);values['fused' if which else 'reference']={'seconds':time.perf_counter()-began,'checksum':int(value)}
    assert values['fused']['checksum']==values['reference']['checksum'];timings.append(values)
result={'pass':True,'positions':len(fens),'cold_seconds':cold,'timings':timings,'scope':'Exact original positional-correction equivalence. Hot-kernel laptop timing only, not full-engine/Linux speed proof.',
        'source_sha256':hashlib.sha256((ROOT/'odin_fused/core_nb.py').read_bytes()).hexdigest()}
(ROOT/'lab/odin/fast/fused-benchmark.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
