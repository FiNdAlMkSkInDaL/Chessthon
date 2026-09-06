"""Original relation features; small convex residual model on existing quiet labels."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,hashlib,time
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(R))
import numpy as np,chess
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(8)['applied']
from lab.odin.training.features_ref import _passed
NAMES=['blocked_passer_advance','safe_passer_path','connected_passer_advance','supported_passer_advance','enemy_king_passer_distance','own_king_passer_distance','undefended_minor_rook','attacked_undefended','restricted_minor','king_open_files','pawn_contact','safe_knight_outpost']
def extract(b):
    rows=[]
    for c in (True,False):
        vals=[0]*len(NAMES);ep=b.pieces_mask(chess.PAWN,not c);ownp=b.pieces_mask(chess.PAWN,c)
        passers=list(s for s in b.pieces(chess.PAWN,c) if _passed(b,c,s))
        for s in passers:
            adv=chess.square_rank(s) if c else 7-chess.square_rank(s);ahead=s+(8 if c else -8)
            if 0<=ahead<64:
                vals[0]+=adv*int(bool(b.piece_at(ahead)))
                path=[chess.square(chess.square_file(s),r) for r in (range(chess.square_rank(s)+1,8) if c else range(chess.square_rank(s)-1,-1,-1))]
                vals[1]+=adv*sum(not b.piece_at(t) and not b.is_attacked_by(not c,t) for t in path)
            vals[2]+=adv*int(any(abs(chess.square_file(s)-chess.square_file(t))==1 and chess.square_distance(s,t)<=1 for t in passers))
            vals[3]+=adv*int(bool(b.attackers_mask(c,s)&ownp))
            vals[4]+=adv*chess.square_distance(b.king(not c),s)
            vals[5]+=adv*chess.square_distance(b.king(c),s)
        for pt in (2,3,4):
            for s in b.pieces(pt,c):
                defended=bool(b.attackers_mask(c,s));attacked=b.is_attacked_by(not c,s)
                vals[6]+=int(not defended);vals[7]+=int(attacked and not defended)
                if pt in (2,3):
                    safe=[t for t in chess.scan_forward(b.attacks_mask(s)&~b.occupied_co[c]) if not (b.attackers_mask(not c,t)&ep)]
                    vals[8]+=max(0,3-len(safe))
                if pt==2:
                    adv=chess.square_rank(s) if c else 7-chess.square_rank(s)
                    vals[11]+=int(adv>=3 and bool(b.attackers_mask(c,s)&ownp) and not bool(b.attackers_mask(not c,s)&ep))
        kf=chess.square_file(b.king(c))
        vals[9]=sum(not (ownp&chess.BB_FILES[f]) for f in range(max(0,kf-1),min(8,kf+2))) * int(bool(b.pieces(chess.QUEEN,not c)))
        vals[10]=sum((chess.BB_PAWN_ATTACKS[c][s]&ep).bit_count() for s in b.pieces(chess.PAWN,c))
        rows.append(vals)
    return np.array(rows[0])-np.array(rows[1])
def metrics(y,p):
    err=np.abs(y-p);return dict(n=len(y),mae_cp=float(err.mean()),rmse_cp=float(np.sqrt(np.mean(err**2))),p90_cp=float(np.quantile(err,.9)))
def ridge(x,y,mask,lam):
    scale=np.sqrt(np.mean(x[mask]**2,axis=0));scale[scale<1e-5]=1;z=x[mask]/scale;t=y[mask];w=np.ones(len(t));coef=np.zeros(x.shape[1])
    for _ in range(8):
        coef=np.linalg.solve(z.T@(z*w[:,None])+lam*np.eye(z.shape[1]),z.T@(w*t));err=np.abs(t-z@coef);w=np.minimum(1,100/np.maximum(err,1e-8))
    return coef/scale
def main():
    out=H/'eval-relations';out.mkdir(exist_ok=True);rows=[json.loads(s) for s in (R/'lab/odin/quiet_eval/fit-records.jsonl').read_text().splitlines()]
    old=np.load(R/'lab/odin/quiet_eval/expanded-matrix.npz');weights=json.loads((R/'lab/odin/quiet_eval/expanded-result.json').read_text());raw=old['features'];phase=old['phase'];xold=np.concatenate([raw*phase,raw*(1-phase)],axis=1)
    v6=old['base']+np.rint(np.clip(xold@np.array(weights['mg']+weights['eg']),-400,400));y=old['y'];train=old['train'];inner=train&np.array([int(hashlib.sha256(('quiet-inner-v1'+r['opening_key']).encode()).hexdigest(),16)%5==0 for r in rows])
    plan=dict(features=NAMES,split='Same original opening-family inner split; previously used outer validation remains descriptive.',labels_sha256=hashlib.sha256((R/'lab/odin/quiet_eval/fit-records.jsonl').read_bytes()).hexdigest(),ridges=[10,100,1000,10000],clip_cp=200,selection='Minimum inner MAE, tie larger ridge; rounded int32 coefficients after refit; no diagnostic-root fitting.')
    (out/'plan.json').write_text(json.dumps(plan,indent=2));start=time.perf_counter();rawnew=np.array([extract(chess.Board(r['fen'])) for r in rows],float);extract_s=time.perf_counter()-start;x=np.concatenate([rawnew*phase,rawnew*(1-phase)],axis=1)
    trials=[]
    for lam in plan['ridges']:
        coef=ridge(x,y-v6,train&~inner,lam);pred=v6+np.clip(x@coef,-200,200);trials.append(dict(ridge=lam,**metrics(y[inner],pred[inner])))
    lam=min(trials,key=lambda t:(t['mae_cp'],-t['ridge']))['ridge'];coef=ridge(x,y-v6,train,lam);quant=np.rint(coef).astype(np.int32)
    result=dict(trials=trials,chosen_ridge=lam,coefficients_float=coef.tolist(),coefficients_int32=quant.tolist(),extraction_seconds=extract_s,metrics={},phase_coverage={},family_overlap=len(set(r['opening_key'] for r in rows if r['split']=='train')&set(r['opening_key'] for r in rows if r['split']!='train')))
    for label,mask in [('train',train),('reused_validation',~train)]:
        result['metrics'][label]={'v6':metrics(y[mask],v6[mask]),'float':metrics(y[mask],(v6+np.clip(x@coef,-200,200))[mask]),'int32':metrics(y[mask],(v6+np.rint(np.clip(x@quant,-200,200)))[mask])}
    for label,mask in [('endgame',phase[:,0]<.25),('middle', (phase[:,0]>=.25)&(phase[:,0]<.75)),('high_material',phase[:,0]>=.75)]:
        valid=mask&~train;result['phase_coverage'][label]=dict(total=int(mask.sum()),valid=int(valid.sum()),v6=metrics(y[valid],v6[valid]),int32=metrics(y[valid],(v6+np.rint(np.clip(x@quant,-200,200)))[valid]))
    result['quantization_mean_abs_cp']=float(np.mean(np.abs(np.clip(x@coef,-200,200)-np.rint(np.clip(x@quant,-200,200)))))
    (out/'result.json').write_text(json.dumps(result,indent=2));np.savez_compressed(out/'matrix.npz',x=x,v6=v6,y=y,train=train,inner=inner);print(json.dumps(result))
if __name__=='__main__':main()
