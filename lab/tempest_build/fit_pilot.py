"""Original king-bucket residual and linear control; frozen family partitions."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,ast,hashlib,json,sys,time
from pathlib import Path
import numpy as np,chess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from lab.odin.training.features_ref import _passed
def metrics(y,p):
    e=np.abs(y-p)
    return dict(n=len(y),mae_cp=float(e.mean()),rmse_cp=float(np.sqrt(np.mean(e*e))),p90_cp=float(np.quantile(e,.9)))
def encode(b):
    indices=[]
    for color in (True,False):
        king=b.king(color)^(0 if color else 56);bucket=(king%8)//2+4*(king//8>=4)
        row=[]
        for sq,p in b.piece_map().items():
            rel=(0 if p.color==color else 6)+p.piece_type-1
            row.append(bucket*768+rel*64+(sq^(0 if color else 56)))
        indices.append(sorted(row)+[6144]*(32-len(row)))
    return indices
def predict(par,x,phase):
    w,b,o=par
    a=np.clip(w[x[:,0]].sum(1)+b,0,1);z=np.clip(w[x[:,1]].sum(1)+b,0,1)
    return np.sum((a-z)*(phase[:,None]*o[:,0]+(1-phase[:,None])*o[:,1]),1)
def fit_net(x,phase,y,weight,tr,va,ridge,seed,maxepochs=60):
    rng=np.random.default_rng(seed);par=[rng.normal(0,.035,(6145,32)).astype(np.float32),np.full(32,.5,np.float32),rng.normal(0,.025,(32,2)).astype(np.float32)];par[0][-1]=0
    m=[np.zeros_like(p) for p in par];v=[p.copy() for p in m];train=np.flatnonzero(tr);step=0;best=(float('inf'),0,None);curve=[]
    for epoch in range(1,maxepochs+1):
        rng.shuffle(train)
        for start in range(0,len(train),128):
            ids=train[start:start+128];xx=x[ids];pp=phase[ids,None];ww=weight[ids];ww=ww/ww.sum();w,b,o=par
            aw=w[xx[:,0]].sum(1)+b;az=w[xx[:,1]].sum(1)+b;a=np.clip(aw,0,1);z=np.clip(az,0,1);taper=pp*o[:,0]+(1-pp)*o[:,1]
            pred=np.sum((a-z)*taper,1);d=np.clip(pred-y[ids],-1,1)*ww
            da=d[:,None]*taper*((aw>0)&(aw<1));dz=-d[:,None]*taper*((az>0)&(az<1))
            gw=np.zeros_like(w)
            for side,grad in [(0,da),(1,dz)]:
                np.add.at(gw,xx[:,side].reshape(-1),np.repeat(grad,32,axis=0))
            gw+=ridge*w;gw[-1]=0
            grads=[gw,da.sum(0)+dz.sum(0),np.stack(((d[:,None]*(a-z)*pp).sum(0),(d[:,None]*(a-z)*(1-pp)).sum(0)),1)+ridge*o]
            step+=1
            for j,(p,g) in enumerate(zip(par,grads)):
                m[j]*=.9;m[j]+=.1*g;v[j]*=.999;v[j]+=.001*g*g
                p-=.003*(m[j]/(1-.9**step))/(np.sqrt(v[j]/(1-.999**step))+1e-8)
            par[0][-1]=0
        score=float(np.mean(np.abs(np.clip(predict(par,x[va],phase[va]),-4,4)-y[va]))*100)
        curve.append([epoch,score])
        if score<best[0]:best=(score,epoch,[p.copy() for p in par])
        if epoch-best[1]>=10:break
    return best,curve
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cpu',type=int,default=8);a=ap.parse_args()
    from lab.laptop_runner import apply_windows_affinity
    if os.name=='nt':assert apply_windows_affinity(a.cpu)['applied']
    out=HERE/'pilot';out.mkdir(exist_ok=False)
    plan=dict(architecture='6144x32 shared eight-king-bucket embedding, color-antisymmetric clipped-ReLU, 32x2 phase output; original random initialization; fixed v6 base',ridges=[.0001,.001,.01],seeds=[260906,260907],max_epochs=60,batch=128,selection='minimum validation MAE; test accessed only for chosen network and chosen linear control',scope='scalar pilot; paired move-ranking and native integration remain separate gates',gate='at least 5cp test MAE gain, no phase p90 damage; then independent move-ranking before integration',pair_loss=False)
    plan['provenance']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'data/states.jsonl',HERE/'data/split-manifest.json',HERE/'data/sampler-identity.json',Path(__file__),*sorted((HERE/'data').glob('labels-?.jsonl'))]}
    (out/'plan.json').write_text(json.dumps(plan,indent=2))
    states={r['id']:r for r in map(json.loads,(HERE/'data/states.jsonl').read_text().splitlines())};labels={}
    for p in sorted((HERE/'data').glob('labels-?.jsonl')):
        rows=list(map(json.loads,p.read_text().splitlines()));assert rows[-1]['type']=='complete'
        for r in rows:
            if r['type']=='label':assert r['id'] not in labels;labels[r['id']]=r['reference']
    assert set(labels)==set(states)
    rows=[r for k,r in states.items() if labels[k].get('white_mate') is None and 'terminal' not in labels[k] and abs(labels[k]['white_cp'])<2000]
    tree=ast.parse((ROOT/'lab/tempest/eval_experiment.py').read_text());functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='extract'];env=dict(np=np,chess=chess,_passed=_passed,NAMES=list(range(12)));exec(compile(ast.Module(body=functions,type_ignores=[]),'<original-relations>','exec'),env)
    boards=[chess.Board(r['fen']) for r in rows];x=np.array([encode(b) for b in boards],np.int32)
    for b in boards[:100]:
        assert encode(b.mirror())==encode(b)[::-1], 'Perspective encoding symmetry'
    phase=np.array([min(24,sum(len(b.pieces(pt,c))*w for pt,w in [(2,1),(3,1),(4,2),(5,4)] for c in (True,False)))/24 for b in boards],np.float32)
    base=np.array([r['static_white_cp'] for r in rows],np.float32);y=np.array([labels[r['id']]['white_cp'] for r in rows],np.float32);target=(y-base)/100
    masks={s:np.array([r['split']==s for r in rows]) for s in ['train','validation','test']};tr,va,te=[masks[s] for s in ['train','validation','test']]
    assert min(tr.sum(),va.sum(),te.sum())>=50
    from collections import Counter
    counts=Counter(r['root_id'] for r in rows);weight=np.array([(1 if r['kind']=='quiet' else .25)/counts[r['root_id']] for r in rows],np.float32)
    raw=np.array([env['extract'](b) for b in boards],np.float64);linear=np.concatenate([raw*phase[:,None],raw*(1-phase[:,None])],1)
    scale=np.sqrt(np.mean(linear[tr]**2,0));scale[scale<1e-6]=1;z=linear/scale
    trials=[];coefs=[]
    for lam in (10,100,1000,10000):
        w=weight[tr].astype(float);coef=np.zeros(z.shape[1]);err=y[tr]-base[tr]
        for _ in range(8):
            coef=np.linalg.solve(z[tr].T@(z[tr]*w[:,None])+lam*np.eye(z.shape[1]),z[tr].T@(w*err));delta=np.abs(err-z[tr]@coef);w=weight[tr]*np.minimum(1,100/np.maximum(delta,1e-8))
        pred=base+np.clip(z@coef,-400,400);trials.append(dict(ridge=lam,**metrics(y[va],pred[va])));coefs.append(coef)
    li=min(range(len(trials)),key=lambda i:trials[i]['mae_cp']);lpred=base+np.clip(z@coefs[li],-400,400)
    nettrials=[];chosen=None;started=time.perf_counter()
    for ridge in plan['ridges']:
        for seed in plan['seeds']:
            best,curve=fit_net(x,phase,target,weight,tr,va,ridge,seed);r=dict(ridge=ridge,seed=seed,validation_mae_cp=best[0],epochs=best[1],curve=curve);nettrials.append(r)
            if chosen is None or best[0]<chosen[0]:chosen=(best[0],r,best[2])
            (out/'trials.json').write_text(json.dumps(nettrials,indent=2));print(ridge,seed,best[:2],flush=True)
    par=chosen[2];wi=np.rint(par[0]*128).astype(np.int16);bi=np.rint(par[1]*128).astype(np.int16);oi=np.rint(par[2]*100*256).astype(np.int16)
    assert np.max(np.abs(par[2]*100*256))<32767,'Output export overflow'
    quant=(wi.astype(np.float32)/128,bi.astype(np.float32)/128,oi.astype(np.float32)/(256*100))
    pred=base+np.rint(np.clip(100*predict(quant,x,phase),-400,400));floatpred=base+np.clip(100*predict(par,x,phase),-400,400)
    result=dict(chosen=chosen[1],linear_trials=trials,linear_chosen=trials[li],data_counts={s:int(m.sum()) for s,m in masks.items()},dropped_mate_terminal_extreme=len(states)-len(rows),metrics={},phase_test={},quantization_mae_cp=float(np.mean(np.abs(pred-floatpred))),seconds=time.perf_counter()-started)
    for split,mask in masks.items():result['metrics'][split]=dict(v6=metrics(y[mask],base[mask]),linear=metrics(y[mask],lpred[mask]),network=metrics(y[mask],pred[mask]))
    for name,mask in [('endgame',phase<=.25),('middle',(phase>.25)&(phase<.75)),('high',phase>=.75)]:
        mask=mask&te
        if mask.sum():result['phase_test'][name]=dict(v6=metrics(y[mask],base[mask]),network=metrics(y[mask],pred[mask]))
    gain=result['metrics']['test']['v6']['mae_cp']-result['metrics']['test']['network']['mae_cp'];tail=all(r['network']['p90_cp']<=r['v6']['p90_cp'] for r in result['phase_test'].values())
    result['scalar_gate_pass']=gain>=5 and tail
    result['decision']='REQUIRE independent move-ranking and native cost gates' if result['scalar_gate_pass'] else 'REJECT integration of this pilot; preserve fitted v6 fallback'
    np.savez_compressed(out/'weights.npz',embedding=wi[:-1],bias=bi,output=oi)
    np.savez_compressed(out/'predictions.npz',target=y,baseline=base,network=pred,linear=lpred,phase=phase,train=tr,validation=va,test=te)
    (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
