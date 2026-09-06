"""Exploratory expansion; uses only original training families to select weights.

The previous validation partition has been inspected. Its new metrics are
descriptive, not a fresh confirmatory gate. The final game holdout is untouched.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from lab.odin.quiet_eval import fit
from lab.odin.training.features_ref import extract as original,FEATURE_NAMES as OLD,_passed
import chess
import numpy as np

NAMES=(*OLD,'bishop_pair','knight_mobility','bishop_mobility','rook_mobility',
       'queen_mobility','king_pressure','passed_quadratic','rook_seventh',
       'pawn_count','knight_count','bishop_count','rook_count','queen_count')
MG=fit.MG_BOUNDS+[(0,80),(0,10),(0,10),(0,10),(0,5),(0,8),(0,12),(0,50)]+[(-50,50)]*5
EG=fit.EG_BOUNDS+[(0,100),(0,10),(0,10),(0,10),(0,5),(0,2),(0,20),(0,80)]+[(-50,50)]*5


def extract(board):
    extras=[]
    for color in (chess.WHITE,chess.BLACK):
        enemy=not color
        pawn_danger=0
        for sq in board.pieces(chess.PAWN,enemy):
            pawn_danger|=chess.BB_PAWN_ATTACKS[enemy][sq]
        safe=chess.BB_ALL & ~board.occupied_co[color] & ~pawn_danger
        zone=chess.BB_KING_ATTACKS[board.king(enemy)]|chess.BB_SQUARES[board.king(enemy)]
        mobility=[]
        pressure=attackers=0
        for pt,weight in ((chess.KNIGHT,2),(chess.BISHOP,2),(chess.ROOK,3),(chess.QUEEN,5)):
            n=0
            for sq in board.pieces(pt,color):
                attacks=board.attacks_mask(sq)
                n+=(attacks&safe).bit_count()
                hits=(attacks&zone).bit_count()
                if hits:
                    pressure+=hits*weight
                    attackers+=1
            mobility.append(n)
        pressure*=min(3,attackers) if board.pieces(chess.QUEEN,color) else 0
        passed=0
        for sq in board.pieces(chess.PAWN,color):
            if _passed(board,color,sq):
                advance=chess.square_rank(sq) if color else 7-chess.square_rank(sq)
                passed+=max(0,advance-2)**2
        seventh=sum(chess.square_rank(sq)==(6 if color else 1) for sq in board.pieces(chess.ROOK,color))
        extras.append([int(len(board.pieces(chess.BISHOP,color))>=2),*mobility,pressure,passed,seventh,
                       *(len(board.pieces(pt,color)) for pt in range(1,6))])
    return (*original(board),*(a-b for a,b in zip(*extras)))


def main():
    plan={'created_utc':datetime.now(timezone.utc).isoformat(),'features':NAMES,'mg_bounds':MG,'eg_bounds':EG,
          'selection':'Original training only: same 20% opening-family inner split; ridge 10/100/1000/10000, Huber100.',
          'limitation':__doc__,'input_sha256':fit.digest(HERE/'fit-records.jsonl')}
    planpath=HERE/'expanded-plan.json'
    assert not planpath.exists(),'Do not overwrite frozen exploratory plan'
    planpath.write_text(json.dumps(plan,indent=2)+'\n')
    rows=[json.loads(s) for s in (HERE/'fit-records.jsonl').read_text().splitlines()]
    xx=[];phase=[]
    for row in rows:
        b=chess.Board(row['fen'])
        xx.append(extract(b))
        phase.append(min(24,sum(len(b.pieces(pt,c))*v for c in chess.COLORS for pt,v in ((2,1),(3,1),(4,2),(5,4))))/24)
    raw=np.array(xx,float);phase=np.array(phase)[:,None]
    x=np.concatenate((raw*phase,raw*(1-phase)),axis=1)
    base=np.array([r['baseline_cp'] for r in rows]);y=np.array([r['reference_cp'] for r in rows])
    train=np.array([r['split']=='train' for r in rows]);valid=~train
    assert train.sum()>4000 and valid.sum()>1000
    inner=train&np.array([int(hashlib.sha256(('quiet-inner-v1'+r['opening_key']).encode()).hexdigest(),16)%5==0 for r in rows])
    fit.MG_BOUNDS=MG;fit.EG_BOUNDS=EG
    choices=[]
    for ridge in (10.,100.,1000.,10000.):
        coef=fit.fitted(x,y-base,train&~inner,ridge)
        choices.append({'ridge':ridge,**fit.metrics(y[inner],base[inner]+np.clip(x[inner]@coef,-400,400))})
    ridge=min(choices,key=lambda r:(r['mae_cp'],-r['ridge']))['ridge']
    coef=np.rint(fit.fitted(x,y-base,train,ridge)).astype(int)
    pred=base+np.rint(np.clip(x@coef,-400,400))
    result={'status':'COMPLETE','plan_sha256':fit.digest(planpath),'features':NAMES,'choices':choices,'ridge':ridge,
            'mg':coef[:len(NAMES)].tolist(),'eg':coef[len(NAMES):].tolist(),
            'metrics':{name:{'rows':int(mask.sum()),'baseline':fit.metrics(y[mask],base[mask]),'fitted':fit.metrics(y[mask],pred[mask])}
                       for name,mask in [('train',train),('reused_validation',valid)]}}
    (HERE/'expanded-result.json').write_text(json.dumps(result,indent=2)+'\n')
    np.savez_compressed(HERE/'expanded-matrix.npz',features=raw,phase=phase,y=y,base=base,train=train)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
