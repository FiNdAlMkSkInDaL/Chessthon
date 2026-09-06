"""Linux-only packing of the exact allowlisted source and verified table data."""
import argparse,hashlib,json,platform,sys,zipfile
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);a=ap.parse_args()
assert sys.platform=='linux' and platform.machine()=='x86_64' and sys.version_info[:2]==(3,12)
root=Path.cwd();sys.path.insert(0,str(root));from lab.release_audit import audit
stage=root/'native'/a.name;expected=json.loads((stage/'source-manifest.json').read_text());audit(stage/'incoming.zip')
src=stage/'source';src.mkdir(exist_ok=False)
with zipfile.ZipFile(stage/'incoming.zip') as z:
    assert set(z.namelist())==set(expected)
    for name,h in expected.items():
        data=z.read(name);assert hashlib.sha256(data).hexdigest()==h
        p=src/name;assert p.resolve().is_relative_to(src.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
final=stage/'candidate-linux-x86.zip'
with zipfile.ZipFile(final,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name in sorted(expected):z.write(src/name,name)
report=audit(final);assert {e['name']:e['sha256'] for e in report['entries']}==expected
with zipfile.ZipFile(final) as z:assert all(e.create_system==3 for e in z.infolist())
for p in src.rglob('*'):
    if p.is_file():p.chmod(0o444)
for p in sorted([p for p in src.rglob('*') if p.is_dir()],key=lambda p:len(p.parts),reverse=True):p.chmod(0o555)
src.chmod(0o555);(stage/'linux-manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(name=a.name,sha256=report['archive_sha256'],bytes=report['uncompressed_bytes'])))
