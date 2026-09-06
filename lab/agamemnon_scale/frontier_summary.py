"""Summarize complete paired-root screens, never infer Elo from teacher regret."""
import json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent/'frontier'
def summarize():
    results={};raw={}
    for p in sorted((HERE/'native').glob('*-results.jsonl')):
        lines=p.read_text().splitlines()
        if not lines or lines[-1]!='{"type": "complete"}':continue
        rows=[json.loads(l) for l in lines]
        if not rows or rows[-1].get('type')!='complete':continue
        name=p.name.removesuffix('-results.jsonl');raw[name]={};entry=dict(cold_seconds=rows[0]['cold_seconds'],checks=next(r for r in rows if r['type']=='checks'))
        for kind in ('nodes','wall'):
            r=[r for r in rows if r['type']=='decision' and r['kind']==kind];assert len(r)==110
            vals=np.array([d['regret'] for d in r]);raw[name][kind]={v['key']:v for v in r}
            entry[kind]=dict(roots=len(r),mean_regret=float(vals.mean()),clipped_500_mean=float(np.minimum(vals,500).mean()),p90=float(np.quantile(vals,.9)),mistakes_over_200=int((vals>200).sum()),nodes=int(np.mean([d['info']['nodes'] for d in r])),mean_depth=float(np.mean([d['info']['depth'] for d in r])),mean_seconds=float(np.mean([d['seconds'] for d in r])))
        results[name]=entry
    if 'tempest' in results:
        for name,d in results.items():
            if name=='tempest':continue
            for kind in ('nodes','wall'):
                diffs=np.array([min(raw['tempest'][kind][key]['regret'],500)-min(r['regret'],500) for key,r in raw[name][kind].items()]);rng=np.random.default_rng(7719);ci=np.quantile([np.mean(rng.choice(diffs,len(diffs))) for _ in range(4000)],[.025,.975]);d[kind]['paired_gain_cp']=float(diffs.mean());d[kind]['paired_bootstrap95']=ci.tolist()
            d['nominate']=bool(d['wall']['paired_gain_cp']>=5 and d['wall']['mistakes_over_200']<=results['tempest']['wall']['mistakes_over_200'] and d['nodes']['paired_gain_cp']>=0)
    (HERE/'decision-results.json').write_text(json.dumps(results,indent=2))
    for name,d in results.items():print(name,json.dumps({k:d[k] for k in ('nodes','wall','nominate') if k in d}))
    return results
if __name__=='__main__':summarize()
