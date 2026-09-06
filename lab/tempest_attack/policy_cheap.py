"""Cost ablation: remove attack scans/check tests from the learned prior."""
import json,hashlib,time
from pathlib import Path
from collections import Counter
from policy_prior import np,fit,ranks,NAMES,apply_windows_affinity
HERE=Path(__file__).resolve().parent
assert apply_windows_affinity(8)['applied']
out=HERE/'policy-cheap';out.mkdir(exist_ok=False);began=time.perf_counter()
drop=[10,11,12,19];keep=[i for i in range(len(NAMES)) if i not in drop]
plan=dict(kept_features=[NAMES[i] for i in keep],removed=[NAMES[i] for i in drop],ridges=[.001,.01],epochs=100,scope='Reused-family development cost ablation. No independent validation or Elo claim.',native_use='Only break zero-history quiet-move ties; hash moves, captures, killers and nonzero history dominate. Original search/evaluation unchanged.')
(out/'plan.json').write_text(json.dumps(plan,indent=2))
m=np.load(HERE/'policy/matrix.npz');raw=m['features'][:,keep];starts=m['starts'];ends=m['ends'];targets=m['targets'];folds=m['folds']
groups=json.loads((HERE/'policy/groups.json').read_text());counts=Counter(r['root_id'] for r in groups);weights=np.array([1/counts[r['root_id']] for r in groups])
x=np.concatenate([raw,np.concatenate([raw[:,6:]*raw[:,p:p+1] for p in range(6)],axis=1)],axis=1)
trials=[];predictions=[]
for lam in plan['ridges']:
    scores=np.zeros(len(raw))
    for fold in range(5):
        coef=fit(x,starts,ends,targets,weights,folds!=fold,lam)
        for g in np.flatnonzero(folds==fold):scores[starts[g]:ends[g]]=x[starts[g]:ends[g]]@coef
    trials.append(dict(ridge=lam,**ranks(scores,starts,ends,targets)));predictions.append(scores);print(trials[-1],flush=True)
choice=max(range(len(trials)),key=lambda i:trials[i]['mrr']);best=trials[choice]
coef=fit(x,starts,ends,targets,weights,np.ones(len(groups),bool),best['ridge'])
nf=raw.shape[1];local=nf-6
collapsed=np.array([[coef[p],*(coef[6:nf]+coef[nf+p*local:nf+(p+1)*local])] for p in range(6)])
assert np.allclose(x@coef,np.sum(np.concatenate([np.ones((len(raw),1)),raw[:,6:]],axis=1)*collapsed[np.argmax(raw[:,:6],axis=1)],axis=1))
control=json.loads((HERE/'policy/result.json').read_text())['pesto_control']
result=dict(plan=plan,trials=trials,chosen=best,pesto_control=control,collapsed_coefficients=collapsed.tolist(),development_gate_pass=best['mrr']-control['mrr']>=.03 and best['top3']-control['top3']>=.05,seconds=time.perf_counter()-began,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),matrix_sha256=hashlib.sha256((HERE/'policy/matrix.npz').read_bytes()).hexdigest())
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({'chosen':best,'development_gate_pass':result['development_gate_pass'],'seconds':result['seconds']}),flush=True)
