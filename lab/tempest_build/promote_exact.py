"""Promote the already Linux-packed, hash-bound conservative Tempest release."""
import hashlib,json,os,shutil,zipfile
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DESKTOP=ROOT.parent
V6='cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647'
NEW='0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
stage=ROOT/'lab/odin/native_release/tempest-exact-r1';candidate=stage/'candidate-linux-x86.zip'
assert sha(candidate)==NEW
gate=json.loads((stage/'native-gate.json').read_text());assert gate['verdict']=='PASS'
smoke=json.loads((HERE/'exact-match/summary.json').read_text());assert smoke['audit']=='PASS' and smoke['smoke_score_guard_pass'] and smoke['games']==12
assert json.loads((HERE/'three-piece/verification.json').read_text())['pass_all']
assert json.loads((HERE/'three-piece/policy-test.json').read_text())['pass_all']
assert json.loads((HERE/'rules-test.json').read_text())['pass_all']
assert not json.loads((HERE/'pilot/result.json').read_text())['scalar_gate_pass']
expected=json.loads((HERE/'exact-manifest.json').read_text())
with zipfile.ZipFile(candidate) as z:
    assert set(z.namelist())==set(expected)
    assert all(e.create_system==3 for e in z.infolist())
    assert {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}==expected
assert {p.name:sha(p) for p in (ROOT/'tempest_exact').iterdir() if p.is_file()}==expected
original=json.loads((HERE/'setup-manifest.json').read_text())['baseline']
assert {p.name:sha(p) for p in (ROOT/'odin_v6').glob('*.py')}==original
assert sha(DESKTOP/'agent.zip')==V6,'signer archive changed: do not overwrite a different user release'
assert sha(DESKTOP/'Odin-v6.zip')==V6
named=DESKTOP/'Tempest-r1.zip';assert not named.exists()
shutil.copyfile(candidate,named);assert sha(named)==NEW
temp=DESKTOP/'agent.tempest-r1-staged.zip';assert not temp.exists()
shutil.copyfile(candidate,temp);assert sha(temp)==NEW
assert sha(DESKTOP/'agent.zip')==V6
os.replace(temp,DESKTOP/'agent.zip')
assert sha(DESKTOP/'agent.zip')==sha(named)==NEW
report=dict(released_utc=datetime.now(timezone.utc).isoformat(),name='Tempest r1',source='tempest_exact',archive_sha256=NEW,previous_v6_sha256=V6,preserved='signer/Odin-v6.zip',desktop_files=['agent.zip','Tempest-r1.zip'],site_upload_performed=False,scope='Conservative rules and exact KQK/KRK improvement. No neural evaluator, general Elo claim, or new full-clock match. Current-rule short smoke plus exact-state proof and native deployment gates.',smoke=smoke)
(stage/'release.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
