"""Check real match bindings and completed games now; never a promotion verdict."""
import json,sys
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.odin.release.plan import digest,lane_plans,validate_plan
from lab.odin.release.validate_match import read_log,validate_metadata,validate_game
stage=ROOT/'lab/odin/native_release/odin-v6-architecture-r1'
planpath=stage/'overnight-plan.json';plan=json.loads(planpath.read_text());validate_plan(plan)
suite=plan['suites']['primary'];errors=[];games=plies=0;lanes=[]
for lane in ('a','b'):
    path=stage/('startup-primary-'+lane+'.jsonl');rows,parse_errors=read_log(path);errors.extend(parse_errors)
    start=rows[0];assert start['type']=='run_start' and start['lane']==lane
    validate_metadata(start,plan,'primary',digest(planpath),errors)
    declared=[asdict(p) for p in lane_plans(suite,lane)];assert start['plans']==declared
    assert start['cpu']==(0 if lane=='a' else 1) and start['pairs_planned']==28
    completed=[r for r in rows if r['type']=='game']
    assert [g['game'] for g in completed]==list(range(1,len(completed)+1))
    assert not any(r['type']=='run_error' for r in rows)
    for game in completed:
        result=validate_game(game,start,declared[game['game']-1],suite,errors)
        assert result is not None;games+=1;plies+=result['plies']
    lanes.append({'lane':lane,'games_checked':len(completed),'source_log_sha256':digest(path)})
result={'pass':not errors,'scope':'Startup metadata and completed-game operational/replay checks only. This is not a completed112-game result or promotion gate.','plan_sha256':digest(planpath),'lanes':lanes,'games_checked':games,'plies_checked':plies,'errors':errors}
(stage/'startup-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert not errors
