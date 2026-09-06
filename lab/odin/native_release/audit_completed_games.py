"""Early evidence-quality check; incomplete samples cannot authorize promotion."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.odin.release.validate_match import read_log,validate_game
from lab.odin.release.plan import lane_plans,validate_plan
stage=ROOT/'lab/odin/native_release/odin-release-r10'
plan=json.loads((stage/'final112/plan.json').read_text(encoding='utf-8'))
validate_plan(plan)
errors=[];replays=[]
for lane in ('a','b'):
    path=stage/f'final112/early-primary-{lane}.jsonl'
    rows,parse_errors=read_log(path)
    errors.extend(parse_errors)
    starts=[r for r in rows if r.get('type')=='run_start']
    assert len(starts)==1
    start=starts[0]
    declared=start['plans']
    for game in (r for r in rows if r.get('type')=='game'):
        replay=validate_game(game,start,declared[game['game']-1],plan['suites']['primary'],errors)
        if replay:replays.append(replay)
report={'scope':'Only completed early games checked for evidence quality. No complete-sample or strength claim.',
        'verdict':'PASS' if not errors else 'FAIL','errors':errors,'games':len(replays),
        'plies':sum(r['plies'] for r in replays),'replays':replays}
(stage/'early-evidence-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='replays'}))
assert not errors
