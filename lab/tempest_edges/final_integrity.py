"""Bind completed research, the unpromoted Linux archive and unchanged release."""
import datetime,hashlib,json,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected=json.loads((ROOT/'lab/tempest_build/exact-manifest.json').read_text())
assert {p.name:sha(p) for p in (ROOT/'tempest_exact').iterdir() if p.is_file() and p.suffix in ('.py','.npz')}==expected
desktop=ROOT.parent/'agent.zip';released='0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4'
assert sha(desktop)==released and sha(ROOT.parent/'Tempest-r1.zip')==released
stage=HERE/'native/tables_guard';gate=json.loads((stage/'native-gate-r2.json').read_text());manifest=json.loads((stage/'linux-manifest.json').read_text())
assert gate['verdict']=='PASS' and gate['structural']['verdict']=='PASS'
assert gate['structural']['original_numba_ready'] and gate['structural']['nopython_root_signatures']
assert gate['structural']['cold_agent_import_s']<55 and gate['protocol']['cold_agent_import_s']<55
archive=stage/'candidate-linux-x86.zip';archive_hash=sha(archive)
assert archive_hash==gate['archive']['sha256']==manifest['archive_sha256']=='6282db3d2f8add9fb9c5636c0b6f3117e05aa6b89400cba9d5ae0fa341b4e2c1'
bundle=json.loads((HERE/'bundle-manifest.json').read_text())
with zipfile.ZipFile(archive) as z:
    assert all(i.create_system==3 for i in z.infolist())
    assert {name:hashlib.sha256(z.read(name)).hexdigest() for name in z.namelist()}==bundle['files']['tables_guard']
assert gate['archive']['uncompressed_bytes']==5295632 and gate['archive']['entry_count']==85
for name,files in bundle['files'].items():
    assert {p.relative_to(HERE/'prototypes'/name).as_posix():sha(p) for p in (HERE/'prototypes'/name).rglob('*') if p.is_file()}==files
results=json.loads((HERE/'results.json').read_text());assert results['audit']=='PASS' and results['total_screen_games']==96
proof=json.loads((HERE/'actual-table-audit.json').read_text());assert proof['audit']=='PASS' and proof['decisions']==90
files={p.relative_to(ROOT).as_posix():sha(p) for p in HERE.rglob('*') if p.is_file() and p.name!='completion-manifest.json'}
for name in ('TEMPEST_COMPOUNDING_RESULTS.md','TEMPEST_ROUND39_REVIEW.md','TEMPEST_COMPOUNDING_PLAN.md'):files['docs/'+name]=sha(ROOT/'docs'/name)
result=dict(audit='PASS',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),desktop_release_sha256=released,
    unpromoted_linux_archive_sha256=archive_hash,native_cold_seconds=gate['structural']['cold_agent_import_s'],official_runner_cold_seconds=gate['protocol']['cold_agent_import_s'],
    screen_games=96,legal_plies=13287,files=files,
    scope='No candidate qualified for independent strength confirmation. No promotion or site upload. Frozen research evidence and usable tablebase implementation retained. Initial lab launcher failure preserved; corrected same-archive native gate passed.')
(HERE/'completion-manifest.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='files'}))
