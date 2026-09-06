"""Pack tested original source/data on Linux; this alone does not authorize promotion."""
import hashlib,json,platform,sys,zipfile
from pathlib import Path
assert sys.platform=='linux' and platform.machine()=='x86_64' and sys.version_info[:2]==(3,12)
root=Path.cwd();sys.path.insert(0,str(root))
from lab.release_audit import audit
expected=json.loads((root/'source-manifest.json').read_text())
assert len(expected)==15 and set(expected)-{'value.npz','three_piece_dtm.npz'}=={n for n in expected if n.endswith('.py')}
audit(root/'incoming.zip');source=root/'source';source.mkdir(exist_ok=False)
with zipfile.ZipFile(root/'incoming.zip') as z:
    assert set(z.namelist())==set(expected)
    for name,h in expected.items():
        assert '/' not in name and '\\' not in name
        data=z.read(name);assert hashlib.sha256(data).hexdigest()==h
        (source/name).write_bytes(data)
archive=root/'candidate-linux-x86.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name in sorted(expected):z.write(source/name,name)
report=audit(archive)
assert {e['name']:e['sha256'] for e in report['entries']}==expected
with zipfile.ZipFile(archive) as z:assert all(e.create_system==3 for e in z.infolist())
for p in source.iterdir():p.chmod(0o444)
source.chmod(0o555)
(root/'linux-manifest.json').write_text(json.dumps(report,indent=2))
print(report['archive_sha256'])
