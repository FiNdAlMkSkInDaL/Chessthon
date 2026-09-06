"""Durable112-game controller and final audit. Never promotes an archive."""
import argparse,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
# Validate the reporting dependency before spending a night on matches.
PINNED=ROOT/'lab/odin/official-harness-91f70e54'
sys.path.insert(0,str(PINNED))
from lab.odin.release import validate_match as _audit_preflight
assert Path(sys.modules['harness.referee'].__file__).resolve().is_relative_to(PINNED)
from lab.odin.release.plan import digest,validate_plan
ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--unit-prefix',required=True);args=ap.parse_args()
out=ROOT/'overnight112';plan_path=out/'plan.json';plan=json.loads(plan_path.read_text());validate_plan(plan)
candidate=ROOT/'candidate-linux-x86.zip';baseline=args.baseline.resolve()
assert digest(candidate)==plan['suites']['primary']['candidate_sha256']
assert digest(baseline)==plan['suites']['primary']['baseline_sha256']
gate=json.loads((ROOT/'native-gate.json').read_text());assert gate['verdict']=='PASS' and gate['archive']['sha256']==digest(candidate)
assert len(plan['suites']['primary']['openings'])==56
assert args.unit_prefix.replace('-','').isalnum()
units=[]
try:
    for lane,cpu in [('a',0),('b',1)]:
        logfile=out/f'primary-{lane}.jsonl';assert not logfile.exists()
        unit=f'{args.unit_prefix}-{lane}'
        command=['systemd-run','--user','--unit='+unit,'--property=WorkingDirectory='+str(ROOT),'--property=RuntimeMaxSec=43200',
                 sys.executable,'-B','-u','-m','lab.odin.release.linux_match','--validation-root',str(ROOT),
                 '--harness-root',str(ROOT/'lab/odin/official-harness-91f70e54'),'--candidate',str(candidate),'--baseline',str(baseline),
                 '--plan',str(plan_path),'--suite','primary','--lane',lane,'--cpu',str(cpu),'--pairs','28',
                 '--openings',str(out/'primary.fen'),'--log',str(logfile)]
        subprocess.run(command,check=True);units.append(unit+'.service')
except BaseException:
    for unit in units:
        subprocess.run(['systemctl','--user','kill','--kill-whom=main','--signal=SIGINT',unit],check=False)
    raise
def progress():
    state={'utc':datetime.now(timezone.utc).isoformat(),'plan_sha256':digest(plan_path),'planned_games':112,'automatic_promotion':False,'lanes':{}}
    for lane,unit in zip(('a','b'),units):
        path=out/f'primary-{lane}.jsonl';rows=[]
        if path.exists():
            for s in path.read_text().splitlines():
                try:rows.append(json.loads(s))
                except json.JSONDecodeError:pass
        games=[r for r in rows if r.get('type')=='game']
        active=subprocess.run(['systemctl','--user','is-active',unit],capture_output=True,text=True).stdout.strip()
        state['lanes'][lane]={'service':unit,'state':active,'games':len(games),'points':sum(r['candidate_points'] for r in games),'errors':[r for r in rows if r.get('type')=='run_error']}
    tmp=out/'progress.tmp';tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(out/'progress.json')
    return state
while True:
    state=progress()
    if not any(lane['state'] in ('active','activating','reloading') for lane in state['lanes'].values()):break
    time.sleep(30)
command=[sys.executable,'-B','-m','lab.odin.release.validate_match','--plan',str(plan_path),'--suite','primary','--out',str(out/'final-audit.json'),str(out/'primary-a.jsonl'),str(out/'primary-b.jsonl')]
result=subprocess.run(command,capture_output=True,text=True,
                      env={**os.environ,'PYTHONPATH':os.pathsep.join((str(PINNED),str(ROOT)))})
(out/'audit.stdout').write_text(result.stdout);(out/'audit.stderr').write_text(result.stderr)
(out/'COMPLETE.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'audit_exit_code':result.returncode,'automatic_promotion':False,'note':'Read final-audit.json and review operational evidence before changing Desktop agent.zip.'},indent=2)+'\n')
raise SystemExit(result.returncode)
