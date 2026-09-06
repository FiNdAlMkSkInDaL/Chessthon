"""Original probability-depth allocator and calibration experiment.
This is a tested search building block, NOT an integrated playing-strength result.
Old out-of-fold quiet policy labels omit captures, margins and refutations.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import json,hashlib,time
from pathlib import Path
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

@njit
def probabilities(logits,temperature,uniform_fraction):
    n=len(logits);out=np.empty(n,np.float64)
    if n==0:return out
    maximum=np.max(logits);total=0.0
    for i in range(n):out[i]=np.exp((logits[i]-maximum)/temperature);total+=out[i]
    for i in range(n):out[i]=(1-uniform_fraction)*out[i]/total+uniform_fraction/n
    return out

@njit
def child_budgets(parent_budget,probs):
    """Uniform prior consumes one depth unit; floor prevents zero-cost cycles.
    Every branch retains positive probability. Tactical mandatory-depth checks
    and alpha-beta re-search semantics belong in the eventual native driver.
    """
    budgets=np.empty(len(probs),np.float64);den=np.log(max(2,len(probs)))
    for i in range(len(probs)):
        cost=max(.5,-np.log(max(probs[i],1e-300))/den)
        budgets[i]=parent_budget-cost
    return budgets

def main():
    z=np.load(ROOT/'lab/tempest_attack/policy/matrix.npz');starts,ends,targets,folds,logits=[z[k] for k in ('starts','ends','targets','folds','oof')]
    checked=0
    for n in (1,2,3,32,218):
        for scale in (0,1,1000):
            s=np.linspace(-scale,scale,n);p=probabilities(s,1,.2);b=child_budgets(10,p)
            assert np.isfinite(p).all() and np.isfinite(b).all() and abs(p.sum()-1)<1e-12 and p.min()>=.2/n-1e-12 and b.max()<=9.5
            if scale==0 and n>1:assert np.max(abs(b-9))<1e-10
            assert np.all(np.diff(b)>=-1e-12);checked+=1
    trials=[]
    for t in (.5,1,2,4):
        for mix in (0,.1,.25,.5):
            logloss=[];uniform=[];under=[];depth=[]
            for st,en,target in zip(starts,ends,targets):
                p=probabilities(logits[st:en],t,mix);at=target-st
                logloss.append(-np.log(max(p[at],1e-300)));uniform.append(np.log(en-st));under.append(p[at]<1/(en-st));depth.append(child_budgets(8,p)[at])
            logloss=np.array(logloss);depth=np.array(depth)
            trials.append(dict(temperature=t,uniform_fraction=mix,nll=float(logloss.mean()),uniform_nll=float(np.mean(uniform)),teacher_below_uniform_fraction=float(np.mean(under)),mean_teacher_child_budget=float(depth.mean()),teacher_budget_p05=float(np.quantile(depth,.05)),fold_nll=[float(logloss[folds==f].mean()) for f in range(5)]))
    # Temperature/floor choice on other folds, report on excluded fold. The
    # underlying policy/hyperparameter choice was already used in prior R&D.
    nested=[]
    for f in range(5):
        choice=min(trials,key=lambda r:np.mean([x for i,x in enumerate(r['fold_nll']) if i!=f]))
        nested.append(dict(fold=f,temperature=choice['temperature'],uniform_fraction=choice['uniform_fraction'],nll=choice['fold_nll'][f]))
    report=dict(checks=checked,groups=len(starts),trials=trials,nested_calibration=nested,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),data_sha256=hashlib.sha256((ROOT/'lab/tempest_attack/policy/matrix.npz').read_bytes()).hexdigest(),scope='Reused development predictions; calibration is not fresh validation. This tests probability budget math, not a complete chess search. It exposes low-prior teacher moves before allocating real depth. Full move alternatives, tactical verification and equal-wall integration remain required.')
    (HERE/'policy-budget.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(checks=checked,groups=len(starts),nested_nll=np.mean([r['nll'] for r in nested]),uniform_nll=trials[0]['uniform_nll'])))
if __name__=='__main__':main()
