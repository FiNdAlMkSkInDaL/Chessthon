"""Distinguish PV stand-pat endpoints from stand-pat beta cutoffs, reusing labels."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,ast,json,hashlib,shutil,sys
from pathlib import Path
import chess,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--stage',action='store_true');ap.add_argument('--lane',type=int,default=0);ap.add_argument('--cpu',type=int,default=2);a=ap.parse_args();src=HERE/'collector-cutinfo'
if a.stage:
    src.mkdir(exist_ok=False)
    for p in (HERE/'collector').iterdir():
        if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
    p=src/'core_nb.py';s=p.read_text();s=s.replace('def provenance_leaf(bb,st,ply,score,trace):','def provenance_leaf(bb,st,ply,score,beta,trace):');s=s.replace('trace[row,29]=score;trace[row,30]=1;trace[row,31]=0','trace[row,29]=score;trace[row,30]=1 if score<beta else 2;trace[row,31]=0');s=s.replace('provenance_leaf(bb,st,ply,stand,nn_acc)','provenance_leaf(bb,st,ply,stand,beta,nn_acc)');p.write_text(s)
    (HERE/'retrace-manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir() if p.suffix in ('.py','.npz')},indent=2));sys.exit(0)
sys.path.insert(0,str(ROOT));from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(a.cpu)['applied'];sys.path.insert(0,str(src))
import agent,core_nb as c
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert c.NUMBA_READY
snapshot={k:v.copy() for k,v in vars(c).items() if isinstance(v,np.ndarray) and v.flags.writeable}
source=(HERE/'collect.py').read_text();source=source.replace('    return res\n',"    if res['provenance']:res['stand_cutoff']=bool(trace[0,30]==2)\n    return res\n")
tree=ast.parse(source);functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('board','search')];assert len(functions)==2
exec(compile(ast.Module(body=functions,type_ignores=[]),'<same-search-cutoff-provenance>','exec'),globals())
rows=[]
for phase in ('pilot','expand'):
    for lane in range(4):
        records=[json.loads(l) for l in (HERE/f'{phase}/lane{lane}.jsonl').read_text().splitlines()];assert records[-1]['type']=='complete';rows.extend(r for r in records if r.get('type')=='root')
rows=rows[a.lane::4];dest=HERE/'settled';dest.mkdir(exist_ok=True)
with (dest/f'lane{a.lane}.jsonl').open('x') as f:
    f.write(json.dumps(dict(type='metadata',manifest=json.loads((HERE/'retrace-manifest.json').read_text()),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),search_driver_sha256=hashlib.sha256((HERE/'collect.py').read_bytes()).hexdigest(),scope='Reuses completed teacher labels. Every traced alternative must retain identical move, score, depth, node count and PV after adding cutoff classification.'))+'\n')
    for i,r in enumerate(rows):
        b=board(r)
        for alt in r['alternatives']:
            old=alt['own']
            if not old['provenance']:continue
            new=search(b,old['uci'])
            for k in ('uci','score','depth','nodes','pv','leaf_fen','leaf_value_white'):assert new[k]==old[k],(r['id'],k,new[k],old[k])
            alt['own']=new
        f.write(json.dumps(r)+'\n');f.flush()
        if i%100==0:print(i,len(rows),flush=True)
    f.write(json.dumps(dict(type='complete'))+'\n')
