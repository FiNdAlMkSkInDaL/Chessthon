"""Family-blocked development CV; all prior pilot splits are USED data.

The CV result is a screening proxy, never a new independent strength gate.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,hashlib,time
from pathlib import Path
import numpy as np,chess
from features import extract,phase,NAMES
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity

def metrics(y,p):
    e=np.abs(y-p)
    return dict(n=len(y),mae=float(e.mean()),p90=float(np.quantile(e,.9)))

def fit(x,y,weight,lam):
    scale=np.maximum(np.sqrt(np.average(x*x,weights=weight,axis=0)),1e-6)
    z=x/scale; w=weight.copy();coef=np.zeros(x.shape[1])
    for _ in range(8):
        gram=z.T@(z*w[:,None])+lam*np.eye(x.shape[1]); rhs=z.T@(y*w)
        for sweep in range(10000):
            prev=coef.copy()
            for j in range(len(coef)):
                coef[j]=max(0,coef[j]+(rhs[j]-gram[j]@coef)/gram[j,j])
            if np.max(np.abs(coef-prev))<1e-8:break
        else:raise AssertionError('Constrained convex solver did not converge')
        gradient=gram@coef-rhs
        assert np.max(np.abs(gradient[coef>1e-6]),initial=0)<1e-3
        assert np.min(gradient[coef<=1e-6],initial=0)>-1e-3
        w=weight*np.minimum(1,100/np.maximum(1,np.abs(y-z@coef)))
    return coef/scale

def main():
    if os.name=='nt':assert apply_windows_affinity(8)['applied']
    out=HERE/'fit';out.mkdir(exist_ok=False);start=time.perf_counter()
    plan=dict(features=NAMES,folds=5,ridges=[10,100,1000],phase_powers=[1,2],clip_cp=600,
      selection='minimum mean absolute error across family-blocked development folds',
      scope='Prior pilot train/validation/test are all used development data; fresh independent confirmation required.',
      gates=['at least 5cp development OOF gain','phase and quiet p90 no worse by more than 5cp','native reference identity and speed','independent decision ranking and paired matches before promotion'],
      coefficient_constraint='nonnegative attack-benefit weights, Huber IRLS ridge, no intercept')
    (out/'plan.json').write_text(json.dumps(plan,indent=2))
    data=ROOT/'lab/tempest_build/data'
    states={r['id']:r for r in map(json.loads,(data/'states.jsonl').read_text().splitlines())};labels={}
    for p in sorted(data.glob('labels-?.jsonl')):
        rs=[json.loads(s) for s in p.read_text().splitlines()];assert rs[-1]['type']=='complete'
        for r in rs:
            if r['type']=='label':labels[r['id']]=r['reference']
    rows=[r for k,r in states.items() if labels[k].get('white_mate') is None and 'terminal' not in labels[k] and abs(labels[k]['white_cp'])<2000]
    boards=[chess.Board(r['fen']) for r in rows]
    raw=np.array([extract(b) for b in boards],float)
    for i,b in enumerate(boards):assert np.array_equal(extract(b.mirror()),-raw[i]),i
    ph=np.array([phase(b) for b in boards]);y=np.array([labels[r['id']]['white_cp'] for r in rows]);base=np.array([r['static_white_cp'] for r in rows])
    fold=np.array([int(hashlib.sha256(('tempest-attack-dev1'+r['family']).encode()).hexdigest()[:8],16)%5 for r in rows])
    from collections import Counter
    counts=Counter(r['root_id'] for r in rows)
    weights=np.array([(1 if r['kind']=='quiet' else .25)/counts[r['root_id']] for r in rows]);weights/=weights.mean()
    trials=[];predictions=[]
    for power in plan['phase_powers']:
        x=raw*ph[:,None]**power
        for lam in plan['ridges']:
            pred=np.zeros(len(rows))
            for f in range(5):
                tr=fold!=f;va=~tr;coef=fit(x[tr],(y-base)[tr],weights[tr],lam)
                pred[va]=base[va]+np.clip(x[va]@coef,-600,600)
            trial=dict(power=power,ridge=lam,**metrics(y,pred));trials.append(trial);predictions.append(pred)
            print(trial,flush=True)
    best=min(range(len(trials)),key=lambda i:trials[i]['mae']);chosen=trials[best];pred=predictions[best]
    coef=fit(raw*ph[:,None]**chosen['power'],y-base,weights,chosen['ridge'])
    slices={}
    for name,mask in [('endgame',ph<=.25),('middle',(ph>.25)&(ph<.75)),('high',ph>=.75),('quiet',np.array([r['kind']=='quiet' for r in rows]))]:
        slices[name]=dict(baseline=metrics(y[mask],base[mask]),candidate=metrics(y[mask],pred[mask]))
    result=dict(plan=plan,trials=trials,chosen=chosen,baseline=metrics(y,base),slices=slices,coefficients=coef.tolist(),features=NAMES,seconds=time.perf_counter()-start)
    result['development_gate_pass']=result['baseline']['mae']-chosen['mae']>=5 and all(s['candidate']['p90']<=s['baseline']['p90']+5 for s in slices.values())
    result['source_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'features.py',data/'states.jsonl',*sorted(data.glob('labels-?.jsonl'))]}
    np.savez_compressed(out/'matrix.npz',raw=raw,phase=ph,target=y,baseline=base,fold=fold,prediction=pred)
    (out/'rows.json').write_text(json.dumps([{'id':r['id'],'family':r['family'],'root_id':r['root_id'],'kind':r['kind']} for r in rows]))
    (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
