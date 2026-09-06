"""Original conditional move-ranking model for quiet search ordering.

Used-family development only. Predicting a teacher move is not proof of Elo.
Only fitted coefficients could enter an engine; no move/FEN lookup data ships.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,hashlib,time
from pathlib import Path
import numpy as np,chess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tempest_exact'))
from eval_nb import MG_TABLE,EG_TABLE
from lab.laptop_runner import apply_windows_affinity
NAMES=['pawn','knight','bishop','rook','queen','king','pesto_delta','from_enemy_pawn','to_enemy_pawn','to_own_pawn','escape_attack','destination_attacked','gives_check','castle','advance_pawn','towards_enemy_king','towards_own_king','king_file','near_enemy_king_pawn','king_zone_gain','open_rook_file','center_gain']

def features(b,m):
    c=b.turn;p=b.piece_type_at(m.from_square);idx=p-1+(0 if c else 6)
    ownk=b.king(c);oppk=b.king(not c);phase=min(24,sum(len(b.pieces(pt,col))*w for pt,w in [(2,1),(3,1),(4,2),(5,4)] for col in (True,False)))
    a=m.from_square;t=m.to_square
    f=np.zeros(len(NAMES),np.float32);f[p-1]=1
    f[6]=((MG_TABLE[idx][t]-MG_TABLE[idx][a])*phase+(EG_TABLE[idx][t]-EG_TABLE[idx][a])*(24-phase))/2400
    ep=b.pieces_mask(chess.PAWN,not c);op=b.pieces_mask(chess.PAWN,c)
    f[7]=bool(chess.BB_PAWN_ATTACKS[c][a]&ep);f[8]=bool(chess.BB_PAWN_ATTACKS[c][t]&ep)
    f[9]=bool(chess.BB_PAWN_ATTACKS[not c][t]&op)
    f[10]=b.is_attacked_by(not c,a);f[11]=b.is_attacked_by(not c,t)
    f[12]=b.gives_check(m);f[13]=b.is_castling(m)
    f[14]=(chess.square_rank(t)-chess.square_rank(a))*(1 if c else -1) if p==1 else 0
    f[15]=chess.square_distance(a,oppk)-chess.square_distance(t,oppk)
    f[16]=chess.square_distance(a,ownk)-chess.square_distance(t,ownk) if p!=6 else 0
    f[17]=int(chess.square_file(t)==chess.square_file(oppk)) if p in (4,5) else 0
    f[18]=int(p==1 and abs(chess.square_file(t)-chess.square_file(oppk))<=1 and chess.square_distance(t,oppk)<=3 and bool(b.pieces_mask(chess.QUEEN,c)))
    oldhits=(b.attacks_mask(a)&chess.BB_KING_ATTACKS[oppk]).bit_count()
    b.push(m);newhits=(b.attacks_mask(t)&chess.BB_KING_ATTACKS[oppk]).bit_count();b.pop()
    f[19]=newhits-oldhits
    f[20]=int(not ((op|ep)&chess.BB_FILES[chess.square_file(t)])) if p==4 else 0
    dist=lambda s:abs(2*chess.square_file(s)-7)+abs(2*chess.square_rank(s)-7)
    f[21]=(dist(a)-dist(t))/4
    return f

def ranks(scores,starts,ends,targets):
    pos=[]
    for start,end,t in zip(starts,ends,targets):
        ss=scores[start:end];v=scores[t]
        # Average rank for ties; no generator-order lottery for the zero prior.
        pos.append(1+np.sum(ss>v)+.5*(np.sum(ss==v)-1))
    pos=np.array(pos)
    return dict(top1=float(np.mean(pos==1)),top3=float(np.mean(pos<=3)),mrr=float(np.mean(1/pos)),mean_rank=float(pos.mean()),groups=len(pos))

def fit(x,starts,ends,targets,weights,train,lam,epochs=100):
    groupids=np.flatnonzero(train);ids=np.concatenate([np.arange(starts[g],ends[g]) for g in groupids])
    xx=x[ids].astype(np.float64);lengths=ends[groupids]-starts[groupids];beg=np.concatenate([[0],np.cumsum(lengths)[:-1]])
    tt=beg+targets[groupids]-starts[groupids];ww=weights[groupids];ww=ww/ww.sum()
    scale=np.sqrt(np.mean(xx*xx,0));scale[scale<1e-5]=1;xx/=scale
    coef=np.zeros(x.shape[1]);moment=coef.copy();variance=coef.copy()
    for epoch in range(1,epochs+1):
        logits=xx@coef;maximum=np.maximum.reduceat(logits,beg)
        ex=np.exp(logits-np.repeat(maximum,lengths));prob=ex/np.repeat(np.add.reduceat(ex,beg),lengths)
        prob[tt]-=1;prob*=np.repeat(ww,lengths)
        grad=xx.T@prob+lam*coef
        moment=.9*moment+.1*grad;variance=.999*variance+.001*grad*grad
        coef-=.04*(moment/(1-.9**epoch))/(np.sqrt(variance/(1-.999**epoch))+1e-8)
    return coef/scale

def main():
    assert apply_windows_affinity(8)['applied'];out=HERE/'policy';out.mkdir(exist_ok=False);started=time.perf_counter()
    plan=dict(features=NAMES,models=['linear','piece_conditioned'],ridges=[.001,.01],folds=5,epochs=100,
      selection='Highest out-of-fold mean reciprocal rank across used development families; retain all trials.',
      gates='At least 0.03 MRR gain and 5 percentage points top-three gain over the original PeSTO-delta control before native integration; independent equal-wall games still required.',
      scope='All prior pilot splits are USED data. Labels nominate one teacher quiet move, not a forced preference margin. This is an ordering proxy, not an evaluation/strength claim.')
    (out/'plan.json').write_text(json.dumps(plan,indent=2))
    data=ROOT/'lab/tempest_build/data';labels={}
    for p in sorted(data.glob('labels-?.jsonl')):
        rows=[json.loads(s) for s in p.read_text().splitlines()];assert rows[-1]['type']=='complete'
        for r in rows:
            if r['type']=='label':labels[r['id']]=r['reference']
    states=[json.loads(s) for s in (data/'states.jsonl').read_text().splitlines()]
    groups=[];raw=[];starts=[];ends=[];targets=[]
    for r in states:
        ref=labels[r['id']]
        if not ref.get('pv_uci') or ref.get('white_mate') is not None or abs(ref['white_cp'])>=1500:continue
        b=chess.Board(r['fen']);teacher=chess.Move.from_uci(ref['pv_uci'][0])
        legal=list(b.legal_moves);assert teacher in legal
        if b.is_capture(teacher) or teacher.promotion or b.is_check():continue
        moves=[m for m in legal if not b.is_capture(m) and not m.promotion]
        if len(moves)<3:continue
        starts.append(len(raw));targets.append(len(raw)+moves.index(teacher))
        for m in moves:
            f=features(b,m);raw.append(f)
            if len(groups)<50:
                mirrored=chess.Move(m.from_square^56,m.to_square^56)
                assert np.allclose(f,features(b.mirror(),mirrored)),(b.fen(),m)
        ends.append(len(raw));groups.append(r)
    raw=np.array(raw);starts=np.array(starts);ends=np.array(ends);targets=np.array(targets)
    folds=np.array([int(hashlib.sha256(('tempest-policy-dev1'+r['family']).encode()).hexdigest()[:8],16)%5 for r in groups])
    from collections import Counter
    counts=Counter(r['root_id'] for r in groups);weights=np.array([1/counts[r['root_id']] for r in groups])
    control=ranks(raw[:,6],starts,ends,targets);trials=[];allcoef=[];preds=[]
    for model in plan['models']:
        x=raw if model=='linear' else np.concatenate([raw,np.concatenate([raw[:,6:]*raw[:,p:p+1] for p in range(6)],axis=1)],axis=1)
        for lam in plan['ridges']:
            predicted=np.zeros(len(raw))
            for fold in range(5):
                coef=fit(x,starts,ends,targets,weights,folds!=fold,lam)
                for g in np.flatnonzero(folds==fold):predicted[starts[g]:ends[g]]=x[starts[g]:ends[g]]@coef
            trial=dict(model=model,ridge=lam,**ranks(predicted,starts,ends,targets));trials.append(trial);preds.append(predicted)
            print(trial,flush=True)
    choice=max(range(len(trials)),key=lambda i:trials[i]['mrr']);best=trials[choice]
    x=raw if best['model']=='linear' else np.concatenate([raw,np.concatenate([raw[:,6:]*raw[:,p:p+1] for p in range(6)],axis=1)],axis=1)
    coef=fit(x,starts,ends,targets,weights,np.ones(len(groups),bool),best['ridge'])
    result=dict(plan=plan,trials=trials,chosen=best,pesto_control=control,coefficients=coef.tolist(),family_count=len(set(r['family'] for r in groups)),legal_quiet_moves=len(raw),seconds=time.perf_counter()-started)
    result['development_gate_pass']=best['mrr']-control['mrr']>=.03 and best['top3']-control['top3']>=.05
    result['source_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),data/'states.jsonl',*sorted(data.glob('labels-?.jsonl'))]}
    (out/'result.json').write_text(json.dumps(result,indent=2))
    np.savez_compressed(out/'matrix.npz',features=raw,starts=starts,ends=ends,targets=targets,folds=folds,oof=preds[choice])
    (out/'groups.json').write_text(json.dumps([dict(id=r['id'],family=r['family'],root_id=r['root_id']) for r in groups]))
    print(json.dumps({k:result[k] for k in ('chosen','pesto_control','family_count','legal_quiet_moves','seconds','development_gate_pass')}),flush=True)
if __name__=='__main__':main()
