"""Apply the frozen local blend-sweep gate after every lane has completed."""
import json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
NAMES=['blend15','blend20','blend25a','blend25b','blend30','blend35']

def main():
    data={}
    for name in NAMES:
        path=HERE/'native'/f'{name}-results.jsonl'
        if not path.exists() or path.read_text().splitlines()[-1]!='{"type": "complete"}':
            print(json.dumps(dict(complete=False,waiting_for=name)));return
        rows=[json.loads(l) for l in path.read_text().splitlines()]
        data[name]={kind:{r['key']:r for r in rows if r.get('type')=='decision' and r['kind']==kind} for kind in ('nodes','wall')}
        assert all(len(v)==110 for v in data[name].values())
    for key,a in data['blend25a']['nodes'].items():
        b=data['blend25b']['nodes'][key]
        assert (a['uci'],a['regret'],a['info']['score'],a['info']['nodes'])==(b['uci'],b['regret'],b['info']['score'],b['info']['nodes'])
    result={}
    for name in NAMES:
        item={}
        for kind in ('nodes','wall'):
            rows=data[name][kind];keys=sorted(rows)
            regret=np.array([min(500,rows[k]['regret']) for k in keys])
            base=np.array([(min(500,data['blend25a'][kind][k]['regret'])+min(500,data['blend25b'][kind][k]['regret']))/2 for k in keys])
            gain=base-regret;rng=np.random.default_rng(617)
            item[kind]=dict(clipped_mean=float(regret.mean()),gain_vs_repeated25=float(gain.mean()),
                bad_200=sum(r['regret']>200 for r in rows.values()),
                paired_bootstrap95=np.quantile(rng.choice(gain,(10000,len(gain))).mean(axis=1),[.025,.975]).tolist())
        result[name]=item
    max_bad=max(result[n]['wall']['bad_200'] for n in ('blend25a','blend25b'))
    for name,r in result.items():
        r['eligible']=name not in ('blend25a','blend25b') and r['wall']['gain_vs_repeated25']>0 and r['wall']['bad_200']<=max_bad and r['nodes']['gain_vs_repeated25']>=0
    eligible=[n for n,r in result.items() if r['eligible']]
    selected=min(eligible,key=lambda n:(result[n]['wall']['clipped_mean'],abs(int(n[5:])-25))) if eligible else None
    control_different=sum(data['blend25a']['wall'][k]['uci']!=r['uci'] for k,r in data['blend25b']['wall'].items())
    report=dict(complete=True,selected_for_direct_match=selected,results=result,
        repeated25_fixed_node_identical=True,repeated25_wall_move_disagreements=control_different,
        scope='Predeclared local sweep on reused110 roots. Root-paired intervals unadjusted for selection; equal allowances, not equal elapsed time. Direct paired games and independent confirmation required; no global optimum claim.')
    (HERE/'blend-results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))

if __name__=='__main__':main()
