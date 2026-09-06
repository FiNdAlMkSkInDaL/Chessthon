"""Compact, explicitly provisional development results; never a promotion gate."""
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median


def summarize(paths):
    games=[]
    for path in paths:
        games.extend(r for line in path.read_text().splitlines() if (r:=json.loads(line)).get('type')=='game')
    assert len({(g['run_id'],g['game']) for g in games})==len(games),'Duplicated evidence'
    roles={role:{'imports':[],'elapsed':[],'depth':[],'nps':[]} for role in ('candidate','baseline')}
    for g in games:
        for color in ('white','black'):
            role=g[color+'_role']
            timing=g[color+'_timing']
            roles[role]['imports'].append(timing['init_s'])
            for t in timing.get('search_telemetry',[]):
                if 'depth' in t:roles[role]['depth'].append(t['depth'])
                if t.get('elapsed_ms',0)>20 and t.get('nodes',0)>0:
                    roles[role]['nps'].append(1000*t['nodes']/t['elapsed_ms'])
    result={'provisional':True,'games':len(games),
            'candidate_hashes':sorted({g['candidate_sha256'] for g in games}),
            'WDL':dict(Counter({1.:'W',.5:'D',0.:'L'}[g['candidate_points']] for g in games)),
            'score':sum(g['candidate_points'] for g in games)/len(games) if games else None,
            'candidate_failures':sum(g['candidate_failure'] for g in games),
            'baseline_failures':sum(g['baseline_failure'] for g in games),
            'terminations':dict(Counter(g['termination'] for g in games)),
            'roles':{r:{k:({'median':median(v),'max':max(v),'n':len(v)} if v else None) for k,v in data.items()} for r,data in roles.items()}}
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('logs',nargs='+',type=Path)
    args=ap.parse_args()
    print(json.dumps(summarize(args.logs),indent=2))
