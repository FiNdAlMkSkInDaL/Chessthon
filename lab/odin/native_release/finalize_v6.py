"""Verify completed frozen evidence; promote only the exact Linux archive."""
import argparse,hashlib,json,os,statistics,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
STAGE=ROOT/'lab/odin/native_release/odin-v6-architecture-r1'
OLD='c7d8972e823eb821c016010445d4b02996daff954d870d63083c445850e21102'
NEW='cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def distribution(values):
    s=sorted(values)
    return {'count':len(s),'minimum':min(s),'median':statistics.median(s),'p95':s[min(len(s)-1,int(.95*len(s)))],'maximum':max(s)}
ap=argparse.ArgumentParser();ap.add_argument('--promote',action='store_true');args=ap.parse_args()
evidence=STAGE/'overnight112';audit=json.loads((evidence/'local-review-audit.json').read_text());remote=json.loads((evidence/'review-audit.json').read_text())
assert audit['verdict']==remote['verdict']=='PASS' and audit['evidence_valid'] and remote['evidence_valid']
assert audit['games_replayed']==112 and audit['statistics']['complete_pairs']==56
assert audit['statistics']['bootstrap']['score_ci'][0]>.5
assert audit['candidate_sha256']==NEW and audit['baseline_sha256']==OLD
assert sha(evidence/'plan.json')==audit['plan_sha256']==remote['plan_sha256']
games=[]
for name,digest in audit['log_sha256'].items():
    assert sha(evidence/name)==digest==remote['log_sha256'][name]
    games.extend(json.loads(s) for s in (evidence/name).read_text().splitlines() if json.loads(s)['type']=='game')
assert len(games)==112
zip_path=STAGE/'candidate-linux-x86.zip';assert sha(zip_path)==NEW
gate=json.loads((STAGE/'native-gate.json').read_text());assert gate['verdict']=='PASS' and gate['archive']['sha256']==NEW
manifest=json.loads((ROOT/'lab/odin/fast/architecture-manifest.json').read_text())
with zipfile.ZipFile(zip_path) as z:
    assert all(i.create_system==3 for i in z.infolist())
    assert {i.filename:hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist()}==manifest['source_hashes']
telemetry={}
for role in ('candidate','baseline'):
    timings=[g[c+'_timing'] for g in games for c in ('white','black') if g[c+'_role']==role]
    assert len(timings)==112
    moves=[m for t in timings for m in t['moves']]
    searches=[s for t in timings for s in t['search_telemetry'] if abs(s['score'])<31000]
    telemetry[role]={'init_s':distribution([t['init_s'] for t in timings]),
        'clock_before_increment_headroom_ms':distribution([m['time_left_ms']-m['elapsed_ms'] for m in moves]),
        'final_clock_ms':distribution([t['moves'][-1]['time_left_ms']-t['moves'][-1]['elapsed_ms']+500 for t in timings if t['moves']]),
        'nonmate_depth':distribution([s['depth'] for s in searches]),
        'observed_nodes_per_second':sum(s['nodes'] for s in searches)/max(1e-9,sum(s['elapsed_ms'] for s in searches)/1000),
        'limitation':'Descriptive game telemetry; roles visited different positions. Use the controlled paired-position benchmark for speed attribution.'}
report={'utc':datetime.now(timezone.utc).isoformat(),'status':'GATED_READY','archive_sha256':NEW,'prior_archive_sha256':OLD,'statistics':audit['statistics'],
        'games_replayed':audit['games_replayed'],'plies_replayed':audit['plies_replayed'],'terminations':dict(Counter(g['termination'] for g in games)),
        'telemetry':telemetry,'evidence_audit_sha256':sha(evidence/'local-review-audit.json'),'plan_sha256':audit['plan_sha256'],
        'audit_repair':'Original post-match report failed with ModuleNotFoundError: harness. Re-ran unchanged validator with pinned official harness on PYTHONPATH, on Linux and Windows; both PASS. Original error retained; no games replayed, removed, changed or relabelled.',
        'website_upload':False}
print(json.dumps(report,indent=2),flush=True)
if args.promote:
    desktop=ROOT.parent;assert sha(desktop/'agent.zip')==OLD and sha(desktop/'Odin-v5.zip')==OLD
    data=zip_path.read_bytes();version=desktop/'Odin-v6.zip'
    if version.exists():assert sha(version)==NEW
    else:
        with version.open('xb') as f:f.write(data)
    tmp=desktop/'agent-v6-promotion.tmp'
    with tmp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    assert sha(tmp)==NEW and sha(desktop/'agent.zip')==OLD
    os.replace(tmp,desktop/'agent.zip')
    assert sha(desktop/'agent.zip')==sha(version)==NEW and sha(desktop/'Odin-v5.zip')==OLD
    report['status']='RELEASED';report['desktop_agent']=str(desktop/'agent.zip')
    report['release_utc']=datetime.now(timezone.utc).isoformat()
    (STAGE/'odin-v6-release.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PROMOTED exact gated Linux Odin v6 ZIP to the signer archive (not in git); v5 preserved.',flush=True)
else:(STAGE/'morning-telemetry-review.json').write_text(json.dumps(report,indent=2)+'\n')
