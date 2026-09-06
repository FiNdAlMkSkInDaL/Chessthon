"""Original symmetric piece-square network, trained from our quiet SF labels.

No published weights or chess-engine code. NumPy is an offline dependency only.
The original validation split has already been inspected: report descriptively.
Select width, regularization, residual baseline and training duration exclusively
on the opening-family inner split of the original training partition.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[k]='1'
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import chess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent

def metrics(y,p):
    e=np.abs(y-p)
    return {'mae_cp':float(e.mean()),'rmse_cp':float(np.sqrt((e*e).mean())),
            'p90_cp':float(np.quantile(e,.9))}

def encode(rows):
    x=np.zeros((len(rows),768),np.float32)
    phase=[]
    for i,r in enumerate(rows):
        b=chess.Board(r['fen'])
        for sq,p in b.piece_map().items():
            x[i,((0 if p.color else 6)+p.piece_type-1)*64+sq]=1
        phase.append(min(24,sum(len(b.pieces(pt,c))*v for c in chess.COLORS for pt,v in ((2,1),(3,1),(4,2),(5,4))))/24)
    flip=np.array([((i//64+6)%12)*64+((i%64)^56) for i in range(768)])
    return x,x[:,flip].copy(),np.array(phase,np.float32)

def predict(par,x,z,phase):
    w,b,o=par
    a=np.clip(x@w+b,0,1);c=np.clip(z@w+b,0,1)
    tapered=phase[:,None]*o[:,0]+(1-phase[:,None])*o[:,1]
    return np.sum((a-c)*tapered,axis=1)

def fit(x,z,phase,y,mask,inner,width,ridge,steps,seed=20260906,monitor=True):
    rng=np.random.default_rng(seed)
    par=[rng.normal(0,.04,(768,width)).astype(np.float32),np.full(width,.5,np.float32),rng.normal(0,.1,(width,2)).astype(np.float32)]
    m=[np.zeros_like(p) for p in par];v=[p.copy() for p in m]
    xx=x[mask];zz=z[mask];pp=phase[mask,None];yy=y[mask]
    best=(1e9,0,None);history=[];started=time.monotonic()
    for step in range(1,steps+1):
        w,b,o=par
        aw=xx@w+b;az=zz@w+b;a=np.clip(aw,0,1);c=np.clip(az,0,1)
        tapered=pp*o[:,0]+(1-pp)*o[:,1]
        pred=np.sum((a-c)*tapered,axis=1)
        d=np.clip(pred-yy,-1,1)/len(yy)
        da=d[:,None]*tapered*((aw>0)&(aw<1));dc=-d[:,None]*tapered*((az>0)&(az<1))
        go=np.stack((np.sum(d[:,None]*(a-c)*pp,axis=0),np.sum(d[:,None]*(a-c)*(1-pp),axis=0)),axis=1)
        grads=[xx.T@da+zz.T@dc+ridge*w,da.sum(0)+dc.sum(0),go+ridge*o]
        for j,(p,g) in enumerate(zip(par,grads)):
            m[j]*=.9;m[j]+=.1*g;v[j]*=.999;v[j]+=.001*g*g
            p-=.008*(m[j]/(1-.9**step))/(np.sqrt(v[j]/(1-.999**step))+1e-8)
        if monitor and (step%10==0 or step==1):
            score=float(np.abs(np.clip(predict(par,x[inner],z[inner],phase[inner]),-4,4)-y[inner]).mean()*100)
            history.append([step,score])
            if score<best[0]:best=(score,step,[p.copy() for p in par])
            if step-best[1]>=70:break
    if not monitor:best=(0,steps,par)
    return best,history,time.monotonic()-started

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cpu',type=int,default=4);ap.add_argument('--output',type=Path,default=HERE/'network-training');args=ap.parse_args()
    if os.name=='nt':
        import sys
        sys.path.insert(0,str(ROOT));from lab.laptop_runner import apply_windows_affinity
        assert apply_windows_affinity(args.cpu)['applied']
    else:os.sched_setaffinity(0,{args.cpu})
    args.output.mkdir(exist_ok=False)
    records=ROOT/'lab/odin/quiet_eval/fit-records.jsonl'
    rows=[json.loads(s) for s in records.read_text().splitlines()]
    x,z,phase=encode(rows);y=np.array([r['reference_cp'] for r in rows],np.float32);base=np.array([r['baseline_cp'] for r in rows],np.float32)
    mat=np.load(ROOT/'lab/odin/quiet_eval/expanded-matrix.npz');old=json.loads((ROOT/'lab/odin/quiet_eval/expanded-result.json').read_text())
    current=base+np.rint(np.clip(np.sum(mat['features']*(phase[:,None]*np.array(old['mg'])+(1-phase[:,None])*np.array(old['eg'])),axis=1),-400,400))
    train=np.array([r['split']=='train' for r in rows]);valid=~train
    inner=train&np.array([int(hashlib.sha256(('quiet-inner-v1'+r['opening_key']).encode()).hexdigest(),16)%5==0 for r in rows])
    plan={'data_sha256':hashlib.sha256(records.read_bytes()).hexdigest(),'architecture':'768 shared piece-square inputs; two color/rank perspectives; clipped ReLU; antisymmetric tapered MG/EG heads; int16 embedding scale256, int16 output scale256; residual cap400cp',
          'grid':{'width':[16,32,64],'ridge':[.0002,.002],'baseline':['pesto','odin']},'selection':'Lowest MAE on original training-family inner split; duration selected there, retrain on all original train. Reused validation descriptive only; final56 opening families untouched.','seed':20260906,'steps_max':400}
    (args.output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    choices=[]
    for mode,offset in [('pesto',base),('odin',current)]:
        target=(y-offset).astype(np.float32)/100
        for width in (16,32,64):
            for ridge in (.0002,.002):
                best,history,seconds=fit(x,z,phase,target,train&~inner,inner,width,ridge,400)
                choice={'baseline':mode,'width':width,'ridge':ridge,'inner_mae_cp':best[0],'epochs':best[1],'seconds':seconds,'history':history}
                choices.append(choice);print(json.dumps(choice),flush=True)
                (args.output/'choices.json').write_text(json.dumps(choices,indent=2)+'\n')
    chosen=min(choices,key=lambda c:(c['inner_mae_cp'],c['width']))
    offset=base if chosen['baseline']=='pesto' else current
    best,_,seconds=fit(x,z,phase,((y-offset)/100).astype(np.float32),train,inner,chosen['width'],chosen['ridge'],chosen['epochs'],monitor=False)
    w,b,o=best[2];wi=np.rint(w*256).astype(np.int16);bi=np.rint(b*256).astype(np.int16);oi=np.rint(o*256).astype(np.int16)
    quant=(wi.astype(np.float32)/256,bi.astype(np.float32)/256,oi.astype(np.float32)/256)
    pred=offset+np.rint(np.clip(100*predict(quant,x,z,phase),-400,400))
    result={'status':'COMPLETE','chosen':chosen,'train':metrics(y[train],pred[train]),'reused_validation':metrics(y[valid],pred[valid]),'odin_validation':metrics(y[valid],current[valid]),'pesto_validation':metrics(y[valid],base[valid]),'quantization_mae_cp':float(np.abs(100*predict(best[2],x,z,phase)-100*predict(quant,x,z,phase)).mean()),'training_seconds':seconds,'choices':choices}
    np.savez_compressed(args.output/'weights.npz',embedding=wi,bias=bi,output=oi)
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='choices'}),flush=True)

if __name__=='__main__':main()
