"""Bounded original architecture/decision-objective experiments, September 6.

All selections use previously exposed development data. Never writes release files.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'): os.environ[k]='1'
import argparse,json,sys,time
from pathlib import Path
import numpy as np
from numba import njit
from turn_model import infer_turn,turn_forward,turn_grad,fit
from train import HERE,ROOT,OLD,adam,metrics,sha

@njit
def contextual(x,counts):
    """Add original piece-relative-to-own-king features to each colour view."""
    result=np.zeros((len(x),2,x.shape[2]*2),np.int32)
    for i in range(len(x)):
        for v in range(2):
            king=-1
            for k in range(counts[i,v]):
                idx=x[i,v,k]
                if idx//64==5:king=idx%64
            assert king>=0
            for k in range(counts[i,v]):
                idx=x[i,v,k];p=idx//64;s=idx%64
                result[i,v,2*k]=idx
                result[i,v,2*k+1]=768+p*225+(s//8-king//8+7)*15+s%8-king%8+7
    return result

def add_context(d):
    z=dict(d);z['x']=contextual(d['x'],d['counts']);z['counts']=d['counts']*2;return z

def dataset(path,cap=None):
    d={k:np.load(path/f'{k}.npy',mmap_mode='r') for k in ('x','counts','phase','base','y','weights','quiet')}
    if cap:
        ids=np.random.default_rng(2026090603).permutation(len(d['y']))[:cap];d={k:v[ids] for k,v in d.items()}
    d['turn']=infer_turn(d['x'],d['counts'],d['phase'],d['base']);return d

def transfer():
    z=dict(np.load(OLD/'public-data/transfer-piece.npz'));z['turn']=infer_turn(z['x'],z['counts'],z['phase'],z['base'])
    return [{k:v[mask] for k,v in z.items()} for mask in (z['split']==0,z['split']!=0)]

def save(p,par):np.savez_compressed(p,w=par[0],bias=par[1],out=par[2])

def architecture(a):
    dest=HERE/f'frontier/{a.kind}-{a.seed}';dest.mkdir(parents=True,exist_ok=False)
    source=HERE/f'turn-aware/s{a.seed}/public.npz';z=np.load(source);par=[z[k].copy() for k in ('w','bias','out')]
    data=dataset(HERE/'data-r2',512000);dev=dict(np.load(HERE/'data-r2/development.npz'));dev['turn']=infer_turn(dev['x'],dev['counts'],dev['phase'],dev['base']);tt,td=transfer()
    if a.kind=='relative':
        oldpred=turn_forward(dev['x'][:100],dev['counts'][:100],dev['phase'][:100],dev['turn'][:100],*par)
        par[0]=np.concatenate([par[0],np.zeros((2700,32),np.float32)])
        data,dev,tt,td=map(add_context,(data,dev,tt,td))
        assert np.max(abs(oldpred-turn_forward(dev['x'][:100],dev['counts'][:100],dev['phase'][:100],dev['turn'][:100],*par)))<1e-6
    plan=dict(kind=a.kind,seed=a.seed,checkpoint_sha256=sha(source),script_sha256=sha(__file__),rows=512000,epochs=4,rate=.0003,adapt_epochs=45,scope='Matched rows/updates/rate; relative arm adds zero-initialized king-relative piece embeddings. Existing development only. Original weights/features. No Elo inference.')
    (dest/'plan.json').write_text(json.dumps(plan,indent=2))
    with (dest/'results.jsonl').open('x') as f:
        def emit(r):f.write(json.dumps(r)+'\n');f.flush()
        par,r,_=fit(data,dev,par,a.seed,4,.0003);save(dest/'public.npz',par);emit(dict(type='public',**r))
        par,r,_=fit(tt,td,par,a.seed,45,.0005);save(dest/'adapted.npz',par);emit(dict(type='adapted',**r));emit(dict(type='complete'))

def policy_rows():
    rows=[]
    for p in sorted((HERE/'policy-exact').glob('labels-?.jsonl')):
        records=[json.loads(l) for l in p.read_text().splitlines()]
        assert records[-1]['type']=='complete'
        rows.extend(r for r in records if 'moves' in r)
    return sorted(rows,key=lambda r:r['key'])

def prepare_decisions():
    import chess
    from representations import encode
    from public_data_prepare import phase,pesto
    dest=HERE/'frontier/decisions';dest.mkdir(parents=True,exist_ok=False)
    children=[];groups=[]
    for r in policy_rows():
        if any(m['mate'] is not None or m['cp'] is None for m in r['moves']):continue
        b=chess.Board(r['fen']);start=len(children)
        for m in r['moves']:
            child=b.copy();child.push_uci(m['uci']);ph=phase(child)
            if child.is_game_over():break
            children.append(dict(fen=child.fen(),x=encode(child,'piece'),phase=ph,base=pesto(child,ph),turn=1 if child.turn else -1))
        else:
            groups.append(dict(**r,start=start,end=len(children),sign=1 if b.turn else -1));continue
        del children[start:]
    n=len(children);x=np.zeros((n,2,32),np.int32);counts=np.zeros((n,2),np.int32)
    for i,c in enumerate(children):
        for v in range(2):counts[i,v]=len(c['x'][v]);x[i,v,:counts[i,v]]=c['x'][v]
    np.savez_compressed(dest/'children.npz',x=x,counts=counts,**{k:np.array([c[k] for c in children],np.int8 if k=='turn' else np.float32) for k in ('phase','base','turn')})
    (dest/'groups.json').write_text(json.dumps(groups));print(json.dumps(dict(groups=len(groups),children=n)))

def pair_loss_grad(d,par,pairs):
    """Smooth pair ordering loss, weight .25 so the Huber derivative stays linear."""
    ix=np.unique(pairs[:,:2].astype(np.int64));sub={k:v[ix] for k,v in d.items()};loc={j:i for i,j in enumerate(ix)}
    pred=turn_forward(sub['x'],sub['counts'],sub['phase'],sub['turn'],*par)
    left=np.array([loc[int(v)] for v in pairs[:,0]]);right=np.array([loc[int(v)] for v in pairs[:,1]]);sign=pairs[:,2]
    gap=sign*(sub['base'][left]/400+pred[left]-sub['base'][right]/400-pred[right])/.5
    deriv=-.5*sign/(1+np.exp(np.clip(gap,-60,60)))
    grads=[]
    for ids,dv in ((left,deriv),(right,-deriv)):
        dd={k:v[ids].copy() for k,v in sub.items()};target=pred[ids]-dv
        _,*g=turn_grad(dd['x'],dd['counts'],dd['phase'],dd['turn'],target,np.ones(len(ids),np.float32),np.arange(len(ids)),*par);grads.append(g)
    return float(np.mean(.25*np.logaddexp(0,-gap))),[a+b for a,b in zip(*grads)]

def regret(groups,d,par):
    value=d['base']+400*turn_forward(d['x'],d['counts'],d['phase'],d['turn'],*par)
    errors=[]
    for r in groups:
        if r['split']!=1:continue
        labels=np.array([m['cp'] for m in r['moves']]);choice=np.argmax(r['sign']*value[r['start']:r['end']]);errors.append(float(labels.max()-labels[choice]))
    return dict(mean=float(np.mean(errors)),p90=float(np.quantile(errors,.9)),bad_200=float(np.mean(np.array(errors)>200)),groups=len(errors))

def rank(a):
    dest=HERE/f'frontier/rank-{a.seed}';dest.mkdir(parents=True,exist_ok=False);source=HERE/'turn-aware/s260909/adapted.npz';z=np.load(source);par=[z[k].copy() for k in ('w','bias','out')]
    d=dict(np.load(HERE/'frontier/decisions/children.npz'));groups=json.loads((HERE/'frontier/decisions/groups.json').read_text());tt,td=transfer();rng=np.random.default_rng(a.seed)
    # Training roots alone generate pairs. Use current-model mistakes plus all inferior alternatives.
    pairs=[]
    for r in groups:
        if r['split']!=0:continue
        labels=np.array([m['cp'] for m in r['moves']]);best=int(np.argmax(labels))
        for j in range(len(labels)):
            if labels[best]-labels[j]>=60:pairs.append((r['start']+best,r['start']+j,r['sign']))
    pairs=np.array(pairs,np.int64);m=[np.zeros_like(p) for p in par];v=[np.zeros_like(p) for p in par];step=0
    strength={260910:.1,260911:.3,260912:1.,260915:0.}[a.seed];target=(tt['y']-tt['base'])/400
    # Numerical check includes sign changes, duplicate endpoints and all parameter types.
    tiny=pairs[:4];loss,gg=pair_loss_grad(d,par,tiny);checks=0
    for pi,p in enumerate(par):
        flat=np.abs(gg[pi]).reshape(-1);indices=np.argsort(flat)[-5:]
        for idx in indices:
            old=p.flat[idx];eps=.001;p.flat[idx]=old+eps;up=pair_loss_grad(d,par,tiny)[0];p.flat[idx]=old-eps;dn=pair_loss_grad(d,par,tiny)[0];p.flat[idx]=old
            assert abs((up-dn)/(2*eps)-gg[pi].flat[idx])<.002,(pi,idx);checks+=1
    best=(regret(groups,d,par)['mean'],0,[p.copy() for p in par]);curve=[]
    for epoch in range(1,13):
        rng.shuffle(pairs)
        for at in range(0,len(pairs),128):
            loss,g=pair_loss_grad(d,par,pairs[at:at+128]);ids=rng.choice(len(target),256)
            _,*replay=turn_grad(tt['x'],tt['counts'],tt['phase'],tt['turn'],target,tt['weights'],ids,*par);step+=1
            for j,p in enumerate(par):adam(p,strength*g[j]+replay[j],m[j],v[j],step,.0001,.02)
        met=regret(groups,d,par);mae=metrics(td['y'],td['base']+400*turn_forward(td['x'],td['counts'],td['phase'],td['turn'],*par))['mae'];curve.append(dict(epoch=epoch,regret=met,transfer_mae=mae));print(epoch,met['mean'],mae,flush=True)
        # Do not trade unlimited static damage for this small preference set.
        if met['mean']<best[0] and mae<240:best=(met['mean'],epoch,[p.copy() for p in par])
    save(dest/'adapted.npz',best[2]);(dest/'result.json').write_text(json.dumps(dict(seed=a.seed,pairs=len(pairs),strength=strength,selected_epoch=best[1],curve=curve,gradient_checks=checks,source_sha256=sha(source),script_sha256=sha(__file__),scope='Finite teacher child-move preference fit with search-state replay; development-root selection; tactical child labels may mismatch static use. Search tests decide.'),indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=('relative','matched','prepare','rank'));ap.add_argument('--seed',type=int,default=260909);ap.add_argument('--cpu',type=int,default=2);a=ap.parse_args()
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(a.cpu)['applied']
    if a.kind=='prepare':prepare_decisions()
    elif a.kind=='rank':rank(a)
    else:architecture(a)
