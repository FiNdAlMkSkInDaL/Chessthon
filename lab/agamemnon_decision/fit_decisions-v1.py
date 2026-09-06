"""Own-search leaf ranking, same-data static control, and replay control."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,json,sys,hashlib
from pathlib import Path
import chess,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'lab/agamemnon_scale'))
from turn_model import turn_forward as shallow_forward,turn_grad as shallow_grad
from frontier import transfer
from train import adam,metrics
from deep_head import forward as deep_forward,grad as deep_grad,initialize as initialize_deep,verify as verify_deep
def turn_forward(x,counts,phase,turn,*par):return (deep_forward if len(par)==6 else shallow_forward)(x,counts,phase,turn,*par)
def turn_grad(x,counts,phase,turn,y,weights,ids,*par):return (deep_grad if len(par)==6 else shallow_grad)(x,counts,phase,turn,y,weights,ids,*par)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(b):return min(' '.join(b.fen().split()[:4]),' '.join(b.mirror().fen().split()[:4]))
def prepare(scope):
    from representations import encode
    from public_data_prepare import phase
    dest=HERE/f'dataset-{scope}';dest.mkdir(exist_ok=True);assert not any(dest.iterdir());roots=[];sources={}
    for folder in (['pilot'] if scope=='pilot' else ['pilot','expand']):
        for lane in range(4):
            p=HERE/f'{folder}/lane{lane}.jsonl';r=[json.loads(l) for l in p.read_text().splitlines()];assert r[-1]['type']=='complete';roots.extend(r for r in r if r.get('type')=='root');sources[str(p.relative_to(HERE))]=sha(p)
    assert len({r['id'] for r in roots})==len(roots)
    leaves=[];groups=[];keysplits={};eligibility=dict(roots=len(roots),alternatives=0,provenance=0,quiet=0)
    for r in roots:
        good=[];eligibility['alternatives']+=len(r['alternatives'])
        for alt in r['alternatives']:
            own,ref=alt['own'],alt['reference'];eligibility['provenance']+=int(own['provenance']);eligibility['quiet']+=int(own.get('quiet',False))
            if not own.get('quiet') or ref['white_cp'] is None or abs(ref['white_cp'])>=2500:continue
            b=chess.Board(own['leaf_fen']);k=canonical(b);keysplits.setdefault(k,set()).add(r['split']);own=dict(own)
            if own.get('hybrid_base_schema')!='white-v2' and not b.turn:
                # Preserve pilot raw files; correct its ancillary hand-feature colour sign.
                from eval_nb import MG_TABLE,EG_TABLE
                mg=eg=0
                for sq,p in b.piece_map().items():
                    pt=p.piece_type-1+(0 if p.color else 6);sign=1 if p.color else -1;mg+=sign*MG_TABLE[pt][sq];eg+=sign*EG_TABLE[pt][sq]
                ph=int(round(24*phase(b)));base=(mg*ph+eg*(24-ph))//24-10;own['hybrid_base_white']=2*base-own['hybrid_base_white'];own['hybrid_base_schema']='white-v2-derived-pilot'
            good.append(dict(**own,y=ref['white_cp'],key=k,split=r['split'],root=r['id']))
        if len(good)>=2 and all(t['reference']['white_mate'] is None for t in r['alternatives']):
            groups.append(dict(id=r['id'],split=r['split'],sign=1 if chess.Board(r['fen']).turn else -1,leaves=good))
    packed=[];final=[]
    for r in groups:
        keep=[l for l in r['leaves'] if len(keysplits[l['key']])==1]
        if len(keep)<2:continue
        start=len(packed);packed.extend(keep);final.append(dict(id=r['id'],split=r['split'],sign=r['sign'],start=start,end=len(packed)))
    n=len(packed);x=np.zeros((n,2,32),np.int32);counts=np.zeros((n,2),np.int32);ph=[];turn=[]
    for i,r in enumerate(packed):
        b=chess.Board(r['leaf_fen']);ph.append(phase(b));turn.append(1 if b.turn else -1)
        for v,z in enumerate(encode(b,'piece')):counts[i,v]=len(z);x[i,v,:len(z)]=z
    data=dict(x=x,counts=counts,phase=np.array(ph,np.float32),turn=np.array(turn,np.int8),base=np.array([r['hybrid_base_white'] for r in packed],np.float32),y=np.array([r['y'] for r in packed],np.float32),split=np.array([r['split'] for r in packed],np.int8))
    z=np.load(ROOT/'lab/agamemnon_scale/turn-aware/s260909/adapted.npz');par=[z[k] for k in ('w','bias','out')]
    pred=data['base']+200*turn_forward(x,counts,data['phase'],data['turn'],*par);observed=np.array([r['leaf_value_white'] for r in packed]);error=float(np.max(abs(pred-observed))) if n else 0;assert error<3.,error
    np.savez_compressed(dest/'data.npz',**data);(dest/'groups.json').write_text(json.dumps(final));(dest/'leaves.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in packed));(dest/'manifest.json').write_text(json.dumps(dict(sources=sources,eligibility=eligibility,kept_leaves=n,training_groups=sum(r['split']==0 for r in final),development_groups=sum(r['split']==1 for r in final),max_float_vs_native_backed_score_error=error,scope='Conditional quiet-leaf alternative groups; regret compares eligible alternatives only. Full legal-move search screening remains required. Cross-split exact/mirror leaves removed.'),indent=2));print((dest/'manifest.json').read_text())

def objective(d,par,pairs,kind):
    indices=pairs[:,:2].reshape(-1).astype(np.int64);ix=np.unique(indices);local={v:i for i,v in enumerate(ix)};sub={k:v[ix] for k,v in d.items()};pred=turn_forward(sub['x'],sub['counts'],sub['phase'],sub['turn'],*par)
    left=np.array([local[v] for v in pairs[:,0]]);right=np.array([local[v] for v in pairs[:,1]]);sgn=pairs[:,2]
    if kind=='pair':
        gap=sgn*((sub['base'][left]-sub['base'][right])/400+.5*(pred[left]-pred[right]))/.5
        dd=-.25*sgn/(1+np.exp(np.clip(gap,-60,60)));loss=float(np.mean(.25*np.logaddexp(0,-gap)));parts=((left,dd),(right,-dd))
    else:
        ids=np.array([local[v] for v in indices]);err=sub['base'][ids]/400+.5*pred[ids]-sub['y'][ids]/400;loss=float(np.mean(np.where(abs(err)<=1,.5*err**2,abs(err)-.5)));parts=((ids,.5*np.clip(err,-1,1)),)
    grads=[np.zeros_like(p) for p in par]
    for ids,deriv in parts:
        dd={k:v[ids].copy() for k,v in sub.items()};target=pred[ids]-deriv
        _,*g=turn_grad(dd['x'],dd['counts'],dd['phase'],dd['turn'],target,np.ones(len(ids),np.float32),np.arange(len(ids)),*par)
        for j in range(len(par)):grads[j]+=g[j]
    return loss,grads

def measure(d,groups,par):
    p=d['base']+200*turn_forward(d['x'],d['counts'],d['phase'],d['turn'],*par);regrets=[];errors=[]
    for r in groups:
        if r['split']!=1:continue
        sl=slice(r['start'],r['end']);teacher=r['sign']*d['y'][sl];choice=np.argmax(r['sign']*p[sl]);regrets.append(float(teacher.max()-teacher[choice]));errors.extend(abs(d['y'][sl]-p[sl]))
    return dict(regret=float(np.mean(regrets)),mae=float(np.mean(errors)),groups=len(regrets),bad_200=int(sum(v>200 for v in regrets)))

def fit(a):
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(a.cpu)['applied'];dest=HERE/f'fits-{a.scope}/{a.kind}-{a.seed}{"-deep" if a.deep else ""}';dest.mkdir(parents=True,exist_ok=False);dataset=HERE/f'dataset-{a.scope}';d=dict(np.load(dataset/'data.npz'));groups=json.loads((dataset/'groups.json').read_text());pairs=[]
    for r in groups:
        if r['split']!=0:continue
        ids=np.arange(r['start'],r['end']);ys=r['sign']*d['y'][ids];best=ids[np.argmax(ys)]
        for idx,y in zip(ids,ys):
            if ys.max()-y>=40:pairs.append((best,idx,r['sign']))
    pairs=np.array(pairs,np.int64);assert len(pairs)>=10,len(pairs)
    replay,olddev=transfer();oldrows=[json.loads(l) for l in (ROOT/'lab/agamemnon/data/rows.jsonl').read_text().splitlines()];oldtr=[r for r in oldrows if r['split']=='train'];devkeys={r['key'] for r in map(json.loads,(dataset/'leaves.jsonl').read_text().splitlines()) if r['split']==1};keep=np.array([canonical(chess.Board(r['fen'])) not in devkeys for r in oldtr]);replay={k:v[keep] for k,v in replay.items()}
    source=ROOT/'lab/agamemnon_scale/turn-aware/s260909/adapted.npz';z=np.load(source);par=[z[k].copy() for k in ('w','bias','out')];deep_checks=None
    if a.deep:
        deep_checks=verify_deep();original=turn_forward(d['x'][:30],d['counts'][:30],d['phase'][:30],d['turn'][:30],*par);par=initialize_deep(par,a.seed);assert np.max(abs(original-turn_forward(d['x'][:30],d['counts'][:30],d['phase'][:30],d['turn'][:30],*par)))<1e-5
    rng=np.random.default_rng(a.seed);mom=[np.zeros_like(p) for p in par];var=[np.zeros_like(p) for p in par];step=0;target=(replay['y']-replay['base'])/400
    # Objective derivative verified independently before updating any model.
    checks=0
    for kind in ('pair','static'):
        loss,g=objective(d,par,pairs[:4],kind)
        for pi,p in enumerate(par):
            for idx in np.argsort(abs(g[pi]).reshape(-1))[-4:]:
                old=p.flat[idx];eps=.001;p.flat[idx]=old+eps;up=objective(d,par,pairs[:4],kind)[0];p.flat[idx]=old-eps;dn=objective(d,par,pairs[:4],kind)[0];p.flat[idx]=old;assert abs((up-dn)/(2*eps)-g[pi].flat[idx])<.002;checks+=1
    baseline=measure(d,groups,par);best=(baseline['regret'],0,[p.copy() for p in par]);curve=[]
    for epoch in range(1,17):
        rng.shuffle(pairs)
        for at in range(0,len(pairs),128):
            sample=pairs[at:at+128];ids=rng.choice(len(target),256);_,*grad=turn_grad(replay['x'],replay['counts'],replay['phase'],replay['turn'],target,replay['weights'],ids,*par)
            for kind,weight in [('pair',1. if a.kind=='pair' else (.5 if a.kind=='mixed' else 0.)),('static',1. if a.kind=='static' else (.5 if a.kind=='mixed' else 0.))]:
                if weight:
                    _,g=objective(d,par,sample,kind)
                    for j in range(len(par)):grad[j]+=weight*g[j]
            step+=1
            for j,p in enumerate(par):adam(p,grad[j],mom[j],var[j],step,.00015,.02)
        met=measure(d,groups,par);oldmae=metrics(olddev['y'],olddev['base']+400*turn_forward(olddev['x'],olddev['counts'],olddev['phase'],olddev['turn'],*par))['mae'];curve.append(dict(epoch=epoch,**met,old_mae=oldmae))
        if oldmae<235 and met['regret']<best[0]:best=(met['regret'],epoch,[p.copy() for p in par])
    np.savez_compressed(dest/'model.npz',**dict(zip(('w','bias','out','u','b2','v'),best[2])));(dest/'result.json').write_text(json.dumps(dict(kind=a.kind,seed=a.seed,deep=a.deep,deep_checks=deep_checks,pairs=len(pairs),baseline=baseline,selected_epoch=best[1],selected_regret=best[0],curve=curve,gradient_checks=checks,updates=step,source_sha256=sha(source),dataset_sha256=sha(dataset/'manifest.json'),script_sha256=sha(__file__),scope='Same fixed pairs, update count, replay draws, initialization and seeds across objectives; identical development checkpoint selection and old-state guard. Semi-gradient on frozen own-search PV leaves, not differentiation through a changed tree.'),indent=2));print(a.kind,a.seed,baseline['regret'],best[0],best[1])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('prepare','fit'));ap.add_argument('--scope',choices=('pilot','full'),default='pilot');ap.add_argument('--kind',choices=('pair','static','mixed','replay'),default='pair');ap.add_argument('--seed',type=int,default=260916);ap.add_argument('--cpu',type=int,default=2);ap.add_argument('--deep',action='store_true');a=ap.parse_args()
    if a.mode=='prepare':prepare(a.scope)
    else:fit(a)
