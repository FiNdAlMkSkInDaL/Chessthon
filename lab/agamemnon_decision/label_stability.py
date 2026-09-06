"""Training-only teacher-budget disagreement diagnostic; no relabelling or tuning."""
import itertools,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
rows=[];changes=[];best_changed=best_total=0;counts={str(t):dict(pairs=0,reversals=0,ties=0) for t in (5,20,40,80)}
for path in sorted((HERE/'settled').glob('lane*.jsonl')):
    for line in path.open():
        r=json.loads(line)
        if r.get('type')!='root' or r['split']!=0:continue
        rows.append(r)
        side=1 if r['fen'].split()[1]=='w' else -1
        ref={a['reference']['uci']:a['reference'] for a in r['alternatives'] if a['reference'].get('white_mate') is None and a['reference'].get('white_cp') is not None}
        common=[a for a in r['teacher_top'] if a.get('white_mate') is None and a.get('white_cp') is not None and a['uci'] in ref]
        for a in common:changes.append(abs(a['white_cp']-ref[a['uci']]['white_cp']))
        if len(common)>1:
            old=max(common,key=lambda a:side*a['white_cp'])['uci']
            new=max(common,key=lambda a:side*ref[a['uci']]['white_cp'])['uci']
            best_changed+=old!=new;best_total+=1
        for a,b in itertools.combinations(common,2):
            first=side*(a['white_cp']-b['white_cp'])
            second=side*(ref[a['uci']]['white_cp']-ref[b['uci']]['white_cp'])
            for threshold,count in counts.items():
                if abs(first)>=int(threshold):
                    count['pairs']+=1;count['reversals']+=first*second<0;count['ties']+=second==0
for count in counts.values():count['reversal_fraction']=count['reversals']/count['pairs'] if count['pairs'] else None
report=dict(training_roots=len(rows),shared_alternatives=len(changes),changed_best_on_common_shortlist=best_changed,common_roots=best_total,
    absolute_cp_change_quantiles=np.quantile(changes,[.5,.9,.99]).tolist(),pair_counts_by_shortlist_gap=counts,
    scope='Training split only. Comparing64k-node MultiPV shortlist estimates with independent forced32k-node labels, on shared nonmate alternatives. Budget/depth/search allocation differs; disagreement measures label sensitivity, not truth or teacher error. No weights, labels, checkpoint selection or confirmation plan changed.')
(HERE/'label-stability.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
