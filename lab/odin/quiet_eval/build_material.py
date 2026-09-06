"""Low-cost alternative: fitted material in existing accumulators plus bishop pair."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from lab.odin.quiet_eval import fit
from lab.odin.storm_plus.build_storm_plus import function_text
import numpy as np


def main():
    source=ROOT/'odin_material'
    assert not source.exists()
    matrix=np.load(HERE/'expanded-matrix.npz')
    indices=[11,19,20,21,22,23]
    raw=matrix['features'][:,indices];phase=matrix['phase']
    x=np.concatenate((raw*phase,raw*(1-phase)),axis=1)
    base,y,train=matrix['base'],matrix['y'],matrix['train']
    rows=[json.loads(s) for s in (HERE/'fit-records.jsonl').read_text().splitlines()]
    inner=train&np.array([int(hashlib.sha256(('quiet-inner-v1'+r['opening_key']).encode()).hexdigest(),16)%5==0 for r in rows])
    fit.MG_BOUNDS=[(0,80)]+[(-50,50)]*5
    fit.EG_BOUNDS=[(0,100)]+[(-50,50)]*5
    plan={'features':['bishop_pair','pawn_count','knight_count','bishop_count','rook_count','queen_count'],
          'mg_bounds':fit.MG_BOUNDS,'eg_bounds':fit.EG_BOUNDS,'ridges':[10,100,1000,10000],
          'choice':'Original train family inner split only; reused validation descriptive.',
          'purpose':'Bake material weights into exact make/unmake accumulators; only pair popcounts added per eval.'}
    (HERE/'material-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    choices=[]
    for ridge in plan['ridges']:
        coef=fit.fitted(x,y-base,train&~inner,ridge)
        choices.append({'ridge':ridge,**fit.metrics(y[inner],base[inner]+np.clip(x[inner]@coef,-400,400))})
    ridge=min(choices,key=lambda r:(r['mae_cp'],-r['ridge']))['ridge']
    coef=np.rint(fit.fitted(x,y-base,train,ridge)).astype(int).tolist()
    pred=base+np.rint(x@np.array(coef))
    result={'choices':choices,'ridge':ridge,'mg':coef[:6],'eg':coef[6:],
            'metrics':{n:{'baseline':fit.metrics(y[m],base[m]),'fitted':fit.metrics(y[m],pred[m])} for n,m in [('train',train),('reused_validation',~train)]}}
    (HERE/'material-result.json').write_text(json.dumps(result,indent=2)+'\n')
    source.mkdir()
    for p in (ROOT/'odin_storm_plus').glob('*.py'):shutil.copy2(p,source/p.name)
    eval_text=(source/'eval_nb.py').read_text()
    mg=[82,337,365,477,1025,0];eg=[94,281,297,512,936,0]
    eval_text=eval_text.replace('MG_VALUE = '+repr(tuple(mg)), 'MG_VALUE = '+repr(tuple([a+b for a,b in zip(mg,coef[1:6]+[0])])) )
    eval_text=eval_text.replace('EG_VALUE = '+repr(tuple(eg)), 'EG_VALUE = '+repr(tuple([a+b for a,b in zip(eg,coef[7:12]+[0])])) )
    fallback=f'''def evaluate(pos, *, adjudicate: bool = False) -> int:
    phase = min(24,sum(int(pos.bb[p]).bit_count()*PHASE_INC[p%6] for p in range(12)))
    pair = int(pos.bb[2].bit_count() >= 2)-int(pos.bb[8].bit_count() >= 2)
    bonus = pair*({coef[0]}*phase+{coef[6]}*(24-phase))//24
    return pesto(pos)+(-bonus if pos.side == BLACK else bonus)
'''
    eval_text=eval_text.replace(function_text(eval_text,'evaluate'),fallback)
    (source/'eval_nb.py').write_text(eval_text,encoding='utf-8')
    core=(source/'core_nb.py').read_text()
    native=f'''@njit(cache=False)
def evaluate_nb(bb, st, adjudicate):
    phase = min(24,np.int64(st[PHASE_ACC]))
    pair = int(popc(bb[2]) >= 2)-int(popc(bb[8]) >= 2)
    bonus = pair*({coef[0]}*phase+{coef[6]}*(24-phase))//24
    if st[SIDE] == 1:
        bonus = -bonus
    return np.int32(pesto_nb(bb,st,True)+bonus)
'''
    core=core.replace(function_text(core,'evaluate_nb'),native)
    (source/'core_nb.py').write_text(core,encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
