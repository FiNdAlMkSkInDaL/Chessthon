"""Small read-only snapshot of the frozen release lanes; no running-game score."""
import hashlib
import json
from pathlib import Path
import subprocess

stage=Path(__file__).resolve().parents[3]
root=stage/'final112'
files={}
for name,want in [('primary-a.jsonl',40),('primary-b.jsonl',40),('guard-a.jsonl',16),('guard-b.jsonl',16)]:
    path=root/name
    if not path.exists():
        files[name]={'games':0,'complete':False,'operational_failures':0,'run_errors':0}
        continue
    raw=path.read_bytes()
    rows=[]
    partial=False
    for line in raw.splitlines():
        try:rows.append(json.loads(line))
        except (json.JSONDecodeError,UnicodeDecodeError):partial=True
    games=[r for r in rows if r.get('type')=='game']
    summaries=[r for r in rows if r.get('type')=='run_summary']
    files[name]={'games':len(games),'complete':len(games)==want and len(summaries)==1 and not partial,
                 'operational_failures':sum(int(bool(r.get('candidate_failure')))+int(bool(r.get('baseline_failure'))) for r in games),
                 'run_errors':sum(r.get('type')=='run_error' for r in rows),
                 'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
active={lane:subprocess.run(['systemctl','--user','is-active','--quiet',f'chesstk-odin-final-r10-{lane}.service']).returncode==0 for lane in ('a','b')}
print(json.dumps({'files':files,'completed_games':sum(r['games'] for r in files.values()),
                  'all_complete':all(r['complete'] for r in files.values()),'active':active,
                  'plan_sha256':hashlib.sha256((root/'plan.json').read_bytes()).hexdigest()}))
