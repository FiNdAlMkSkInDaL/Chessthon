"""Resume-safe final evidence retrieval and conditional exact-byte promotion.

Uses the already authorized SSH destination from a process environment variable;
never writes that destination or credentials to artifacts. A STOP-FINALIZATION
file in the release stage cancels this helper. It never uploads to the site.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[3]
STAGE=ROOT/'lab/odin/native_release/odin-release-r10'
FINAL=STAGE/'final112'
REPORT=ROOT/'lab/odin/promotion/reports/final-r10'
PLAN='26551be568a8e2fc7eaeb60530fd2c3934c86c8056021c7db840e7414c686734'
OPTIONS=['-q','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','ConnectTimeout=10']
REMOTE='chess-sign-odin-20260905/odin-release-r10'
SNAPSHOT='"$HOME/chess-tk/.venv/bin/python" "$HOME/'+REMOTE+'/lab/odin/native_release/final_snapshot.py"'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    destination=os.environ.pop('ODIN_RELEASE_SIGNER_DESTINATION')
    assert sha(FINAL/'plan.json')==PLAN
    status_path=STAGE/'finalizer-status.json'
    def status(event,**extra):
        value={'event':event,'utc':datetime.now(timezone.utc).isoformat(),**extra}
        temp=status_path.with_suffix('.tmp')
        temp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        os.replace(temp,status_path)
        print(json.dumps(value),flush=True)
    began=time.monotonic();previous=None;network_failures=0
    status('WAITING_FOR_FIXED_112_GAME_TEST')
    while time.monotonic()-began<13*3600:
        if (STAGE/'STOP-FINALIZATION').exists():
            status('CANCELLED_NO_PROMOTION');return 2
        try:
            remote=subprocess.run(['ssh',*OPTIONS,destination,SNAPSHOT],capture_output=True,text=True,timeout=45)
        except (subprocess.TimeoutExpired,OSError):
            remote=None
        if remote is None or remote.returncode:
            network_failures+=1
            if network_failures==1:status('CONNECTION_RETRY_NO_PROMOTION',completed_games=previous)
            time.sleep(55);continue
        network_failures=0
        snapshot=json.loads(remote.stdout)
        assert snapshot['plan_sha256']==PLAN
        count=snapshot['completed_games']
        if count!=previous:
            status('MATCHES_RUNNING',completed_games=count,total_games=112,files=snapshot['files'],active=snapshot['active'])
            previous=count
        if snapshot['all_complete']:
            break
        if not any(snapshot['active'].values()):
            status('CONTROLLERS_STOPPED_INCOMPLETE_NO_PROMOTION',completed_games=count);return 3
        time.sleep(55)
    else:
        status('WAIT_LIMIT_NO_PROMOTION',completed_games=previous);return 4
    assert snapshot['completed_games']==112
    for name,details in snapshot['files'].items():
        if (STAGE/'STOP-FINALIZATION').exists():
            status('CANCELLED_NO_PROMOTION');return 2
        target=FINAL/name
        if target.exists() and sha(target)==details['sha256']:continue
        temp=target.with_suffix('.download')
        transfer=subprocess.run(['scp',*OPTIONS,f'{destination}:{REMOTE}/final112/{name}',str(temp)],capture_output=True,text=True,timeout=45)
        if transfer.returncode or not temp.exists() or sha(temp)!=details['sha256']:
            status('EVIDENCE_TRANSFER_FAILED_NO_PROMOTION',file=name);return 5
        os.replace(temp,target)
    status('VALIDATING_ALL_EVIDENCE',completed_games=112)
    command=[sys.executable,'-B','-m','lab.odin.promotion.promote',
             '--candidate',str(STAGE/'candidate-linux-x86.zip'),'--source',str(ROOT/'odin_submission'),
             '--plan',str(FINAL/'plan.json'),'--gate',str(STAGE/'native-gate.json'),
             '--primary-logs',str(FINAL/'primary-a.jsonl'),str(FINAL/'primary-b.jsonl'),
             '--guard-logs',str(FINAL/'guard-a.jsonl'),str(FINAL/'guard-b.jsonl'),
             '--report-dir',str(REPORT)]
    gate=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=300)
    (STAGE/'final-validation.stdout.txt').write_text(gate.stdout,encoding='utf-8')
    (STAGE/'final-validation.stderr.txt').write_text(gate.stderr,encoding='utf-8')
    if gate.returncode:
        status('RELEASE_GATE_FAILED_NO_PROMOTION',report=str(REPORT.relative_to(ROOT)));return 6
    if (STAGE/'STOP-FINALIZATION').exists():
        status('CANCELLED_AFTER_VALIDATION_NO_PROMOTION');return 2
    result=subprocess.run(command+['--apply'],cwd=ROOT,capture_output=True,text=True,timeout=300)
    (STAGE/'final-promotion.stdout.txt').write_text(result.stdout,encoding='utf-8')
    (STAGE/'final-promotion.stderr.txt').write_text(result.stderr,encoding='utf-8')
    if result.returncode:
        status('PROMOTION_FAILED_SEE_REPORT',report=str(REPORT.relative_to(ROOT)));return 7
    report=json.loads((REPORT/'odin-release.json').read_text(encoding='utf-8'))
    assert report['mode']=='applied' and report['verdict']=='PASS'
    assert sha(ROOT.parent/'agent.zip')==report['candidate']['sha256']
    primary=report['match_audits']['primary']['statistics']
    guard=report['match_audits']['guard']['statistics']
    progress=ROOT/'docs/ODIN_RELEASE_PROGRESS.md'
    notice=(f"# Odin v5 ready outside git\n\nApplied {report['applied_utc']}. "
            f"signer `agent.zip` and `Odin-v5.zip` are the exact tested Linux archive, "
            f"SHA-256 `{report['candidate']['sha256']}`. Storm/v3 backups are preserved. "
            f"Primary80: {primary['wins']}W/{primary['draws']}D/{primary['losses']}L, "
            f"score{primary['score']:.1%}, paired95% CI{primary['bootstrap']['score_ci']}. "
            f"Original-Storm guard32: {guard['wins']}W/{guard['draws']}D/{guard['losses']}L. "
            "All evidence and zero-fault gates passed. No site upload was performed. "
            "Full report: `lab/odin/promotion/reports/final-r10/ODIN_RELEASE_REPORT.md`.\n\n"
            "The following is historical work-in-progress context, superseded by this release.\n\n")
    progress.write_text(notice+progress.read_text(encoding='utf-8'),encoding='utf-8')
    status('ODIN_READY_ON_DESKTOP',sha256=report['candidate']['sha256'],report=str(REPORT.relative_to(ROOT)),
           primary=primary,guard=guard)
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        # Exception text from network subprocesses can include host information.
        print(json.dumps({'event':'FINALIZER_EXCEPTION_NO_FURTHER_ACTION','exception_type':type(exc).__name__}),flush=True)
        raise SystemExit(10)
