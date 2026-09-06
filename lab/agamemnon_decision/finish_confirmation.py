"""Finish the authorized one-off match audit; never promote or start extra games."""
import json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];out=ROOT/'confirmation24'
units=['agamemnon-confirm-a.service','agamemnon-confirm-b.service']
deadline=time.monotonic()+4*3600+300
while True:
    states={u:subprocess.run(['systemctl','--user','is-active',u],capture_output=True,text=True).stdout.strip() for u in units}
    if not any(s in ('active','activating','reloading') for s in states.values()):break
    if time.monotonic()>deadline:
        raise TimeoutError('Match audit wait exceeded bound; inspect services without killing unrelated work')
    time.sleep(20)
audit=subprocess.run([sys.executable,str(Path(__file__).with_name('audit_confirmation.py')),'--directory',str(out)],capture_output=True,text=True)
(out/'audit.stdout').write_text(audit.stdout);(out/'audit.stderr').write_text(audit.stderr)
report=json.loads((out/'audit.json').read_text()) if (out/'audit.json').exists() else {}
complete=dict(utc=datetime.now(timezone.utc).isoformat(),audit_exit_code=audit.returncode,
    states=states,evidence_valid=report.get('evidence_valid',False),bounded_confirmation_pass=report.get('bounded_confirmation_pass',False),
    automatic_promotion=False,note='Read audit.json. A valid inconclusive statistical result is distinct from an operational/audit failure. Desktop remains Tempest.')
(out/'COMPLETE.json').write_text(json.dumps(complete,indent=2))
print(json.dumps(complete),flush=True)
raise SystemExit(audit.returncode)
