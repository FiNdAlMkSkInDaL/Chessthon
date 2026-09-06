"""Audit complete fixed-root Linux decisions and controlled training outcomes."""
import json,hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def main():
    result={};raw={}
    for p in sorted((HERE/'native').glob('*-results.jsonl')):
        lines=p.read_text().splitlines()
        if not lines or lines[-1]!='{"type": "complete"}':continue
        rows=[json.loads(l) for l in lines];name=p.name.removesuffix('-results.jsonl');entry=dict(cold_seconds=rows[0]['cold_seconds'],checks=next(r for r in rows if r['type']=='checks'));raw[name]={}
        for kind in ('nodes','wall'):
            r=[r for r in rows if r.get('type')=='decision' and r['kind']==kind];assert len(r)==110
            raw[name][kind]={v['key']:v for v in r};vals=np.array([d['regret'] for d in r]);entry[kind]=dict(mean_regret=float(vals.mean()),clipped_mean=float(np.minimum(vals,500).mean()),bad_200=int((vals>200).sum()),mean_nodes=float(np.mean([d['info']['nodes'] for d in r])),mean_depth=float(np.mean([d['info']['depth'] for d in r])),mean_seconds=float(np.mean([d['seconds'] for d in r])))
        result[name]=entry
    if 'tempest' in result:
        for name,d in result.items():
            for kind in ('nodes','wall'):
                diffs=np.array([min(raw['tempest'][kind][k]['regret'],500)-min(v['regret'],500) for k,v in raw[name][kind].items()]);rng=np.random.default_rng(616);d[kind]['paired_gain_cp']=float(diffs.mean());d[kind]['bootstrap95']=np.quantile([rng.choice(diffs,len(diffs)).mean() for _ in range(3000)],[.025,.975]).tolist()
            d['nominate']=name not in ('tempest','mix25','mix50','blend25a','blend25b') and d['wall']['paired_gain_cp']>=5 and d['wall']['bad_200']<=result['tempest']['wall']['bad_200'] and d['nodes']['paired_gain_cp']>=0
    fits=[]
    for p in sorted(HERE.glob('fits-*/*/result.json')):
        r=json.loads(p.read_text());fits.append(dict(name=str(p.parent.relative_to(HERE)),kind=r['kind'],seed=r['seed'],deep=r.get('deep',False),soft=r.get('soft',False),pairs=r['pairs'],updates=r['updates'],selected_epoch=r['selected_epoch'],selected_regret=r['selected_regret'],baseline=r['baseline'],last=r['curve'][-1],source_sha256=r['source_sha256'],dataset_sha256=r['dataset_sha256']))
    report=dict(complete_variants=len(result),decisions=220*len(result),variants=result,fits=fits,scope='Reused110-root development tests and unadjusted paired-root bootstrap; not Elo, independent confirmation or source-level competition certification.')
    (HERE/'results.json').write_text(json.dumps(report,indent=2))
    for name,r in result.items():print(name,'nodes',round(r['nodes']['clipped_mean'],2),'wall',round(r['wall']['clipped_mean'],2),'large',r['wall']['bad_200'],'nominate',r.get('nominate'))
if __name__=='__main__':main()
