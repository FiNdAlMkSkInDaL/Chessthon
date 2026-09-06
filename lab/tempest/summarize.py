"""Regenerate descriptive tables. No claim of unbiased engine Elo."""
import json,collections,statistics,math
from pathlib import Path
H=Path(__file__).resolve().parent
def read(p):return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
def main():
    cases={c['id']:c for c in json.loads((H/'corpus-v1.json').read_text())};plan=json.loads((H/'experiment-plan.json').read_text());focus=set(plan['focus'])
    if (H/'opponent-critical.json').exists():cases.update({c['id']:c for c in json.loads((H/'opponent-critical.json').read_text())})
    refs={(r['id'],r['uci']):r['reference'] for r in read(H/'reference-choices.jsonl') if r.get('type')=='choice'}
    probes={};metadata={}
    for v in plan['variants']:
        rows=read(H/(v+'-probes.jsonl'));probes[v]={(r['id'],r['mode'],r['budget']):r for r in rows if r.get('type')=='probe'};metadata[v]={'complete':any(r.get('type')=='complete' for r in rows),'n':len(probes[v]),'isolation':any(r.get('pass_ABA') for r in rows)}
    def cp(cid,u):
        ref=refs.get((cid,u))
        if not ref or ref.get('white_mate') is not None:return None
        return ref['white_cp']*(1 if cases[cid]['storm_colour']=='white' else -1)
    best={}
    for (cid,u),ref in refs.items():
        score=cp(cid,u)
        if score is not None:best[cid]=max(best.get(cid,-100000),score)
    def regret(r):
        v=cp(r['id'],r['uci']);return None if v is None else max(0,best[r['id']]-v)
    table=[]
    for v,rs in probes.items():
        for mode,budget in [('nodes',200000),('nodes',1000000),('wall',1500)]:
            paired=[]
            for key,r in rs.items():
                if key[0] not in focus or key[1:]!=(mode,budget) or key not in probes['baseline']:continue
                b=probes['baseline'][key];x,y=regret(r),regret(b)
                if x is not None and y is not None:paired.append((r,b,x,y))
            if paired:table.append(dict(variant=v,mode=mode,budget=budget,n=len(paired),mean_candidate_set_regret_cp=statistics.mean(t[2] for t in paired),mean_delta_vs_v6_cp=statistics.mean(t[2]-t[3] for t in paired),improve_ge30=sum(t[3]-t[2]>=30 for t in paired),worsen_ge30=sum(t[2]-t[3]>=30 for t in paired),same_move=sum(t[0]['uci']==t[1]['uci'] for t in paired),median_depth=statistics.median(t[0]['info']['depth'] for t in paired),total_seconds=sum(t[0]['seconds'] for t in paired)))
    budgetcurve=[]
    for cid in focus:
        lo=probes['baseline'].get((cid,'nodes',200000));hi=probes['baseline'].get((cid,'nodes',1000000))
        if lo and hi and regret(lo) is not None and regret(hi) is not None:budgetcurve.append(dict(id=cid,lo_uci=lo['uci'],hi_uci=hi['uci'],improvement_cp=regret(lo)-regret(hi),low_regret=regret(lo),high_regret=regret(hi)))
    opponents=[]
    manifest={r['game_id']:r for r in json.loads((H/'public/games.json').read_text())}
    for cid,c in cases.items():
        if c['source_kind']!='public' or c['split']!='discovery':continue
        r=probes['baseline'].get((cid,'nodes',200000));actual=cp(cid,c['played_uci'])
        if r is None or actual is None or cp(cid,r['uci']) is None:continue
        m=manifest[c['game_id']];player=m['headers']['White' if c['storm_colour']=='white' else 'Black']
        opponents.append(dict(id=cid,player=player,opponent=m['headers']['Black' if c['storm_colour']=='white' else 'White'],played=c['played_san'],v6=r['san'],actual_minus_v6_cp=actual-cp(cid,r['uci']),actual_clock_ms=c['time_left_ms'],game_id=c['game_id'],fen=c['fen']))
    labels=read(H/'label-audit.jsonl');d=sorted(abs(r['delta_cp']) for r in labels)
    data=dict(metadata=metadata,table=table,budget_curve=budgetcurve,opponent_roots=opponents,label_audit={'n':len(d),'mean_abs_delta_cp':statistics.mean(d),'median_abs_delta_cp':statistics.median(d),'ge50':sum(x>=50 for x in d),'ge100':sum(x>=100 for x in d)},reference_moves=len(refs),limitations='Candidate-set regret uses the maximum of same-budget 1M restricted root analyses among measured moves; non-mate only. Candidate pool selected by interventions, finite reference instability remains. It is not exhaustive minimax regret, a random sample, or an Elo estimate. ARM wall tests are exploratory and occurred alongside other CPU-affined work.')
    (H/'summary.json').write_text(json.dumps(data,indent=2))
    lines=['| Variant | Budget | n | Mean regret cp | Delta vs v6 cp | Improved / worse >=30cp | Same move | Median depth |','|---|---|---:|---:|---:|---|---:|---:|']
    for t in table:lines.append(f"| {t['variant']} | {t['mode']} {t['budget']} | {t['n']} | {t['mean_candidate_set_regret_cp']:.1f} | {t['mean_delta_vs_v6_cp']:+.1f} | {t['improve_ge30']} / {t['worsen_ge30']} | {t['same_move']} | {t['median_depth']} |")
    (H/'tables.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
if __name__=='__main__':main()
