"""Preselect diagnostics from site mistakes, without consulting Odin answers."""
import argparse
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser()
ap.add_argument('--rounds',type=int,nargs='+',default=list(range(26,30)))
ap.add_argument('--output',type=Path,default=HERE/'selected-roots.json')
ap.add_argument('--max-cases',type=int,default=3)
ap.add_argument('--min-score',type=int)
args=ap.parse_args()
selected=[]
summary=[]
for rnd in args.rounds:
    rows=[json.loads(s) for s in (HERE/f'round-{rnd}-screen.jsonl').read_text(encoding='utf-8').splitlines()]
    assert rows[-1]['type']=='summary' and rows[-1]['holdout_exact_position_overlap_plies']==[]
    positions={r['ply']:r for r in rows if r['type']=='position'}
    assert len(positions)==rows[-1]['positions']
    candidates=[]
    for ply,r in positions.items():
        if not r['storm_turn'] or not r['played_uci'] or r.get('terminal'):continue
        after=positions[ply+1]
        if r.get('white_mate') is not None or after.get('white_mate') is not None:continue
        sign=1 if r['storm_colour']=='white' else -1
        if args.min_score is not None and sign*r['white_cp']<args.min_score:continue
        drop=sign*(r['white_cp']-after['white_cp'])
        if abs(r['white_cp'])>1500 or abs(after['white_cp'])>1500:continue
        candidates.append(dict(r,screen_drop_cp=drop,screen_before_stm=sign*r['white_cp'],screen_after_stm=sign*after['white_cp']))
    picked=[]
    for r in sorted(candidates,key=lambda x:x['screen_drop_cp'],reverse=True):
        if any(abs(r['ply']-p['ply'])<6 for p in picked):continue
        picked.append(dict(r,selection_reason='Top spaced non-mate own-move reference drop; finite screen, requires same-root confirmation.'))
        if len(picked)==args.max_cases:break
    if rnd==29:
        # Old Storm had a 300-ply material mode. Test either side of that boundary.
        for absolute in (289,301,389):
            r=next(x for x in positions.values() if x['absolute_ply']==absolute)
            assert r['storm_turn'] and r['played_uci']
            if not any(p['ply']==r['ply'] for p in picked):
                picked.append(dict(r,selection_reason='Long game / obsolete 300-ply adjudication / late fifty-clock diagnostic.'))
    for r in picked:r['id']=f"site-r{rnd}-ply{r['ply']}"
    selected.extend(picked)
    summary.append({'round':rnd,'result':rows[0]['headers']['Result'],'positions':len(positions),'selected':[{'id':r['id'],'move':r['played_san'],'absolute_ply':r['absolute_ply'],'screen_drop_cp':r.get('screen_drop_cp'),'screen_before_stm':r.get('screen_before_stm'),'clock_ms':r['time_left_ms']} for r in picked]})
out=args.output
assert not out.exists()
out.write_text(json.dumps(selected,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
