"""Pack exactly the tested source plus original endgame data on Linux."""
from pathlib import Path
import json,platform,sys,zipfile,hashlib
def main():
    assert sys.platform=='linux' and platform.machine()=='x86_64' and sys.version_info[:2]==(3,12)
    root=Path.cwd();sys.path.insert(0,str(root));from lab.release_audit import audit
    expected=json.loads((root/'exact-source-manifest.json').read_text())
    assert len(expected)==14 and set(expected)-{'three_piece_dtm.npz'}=={k for k in expected if k.endswith('.py')}
    audit(root/'incoming.zip');src=root/'source';src.mkdir(exist_ok=False)
    with zipfile.ZipFile(root/'incoming.zip') as z:
        assert set(z.namelist())==set(expected)
        for name,h in expected.items():
            assert '/' not in name and '\\' not in name
            data=z.read(name);assert hashlib.sha256(data).hexdigest()==h;(src/name).write_bytes(data)
    final=root/'candidate-linux-x86.zip'
    with zipfile.ZipFile(final,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted(expected):z.write(src/name,name)
    report=audit(final);assert {e['name']:e['sha256'] for e in report['entries']}==expected
    with zipfile.ZipFile(final) as z:assert all(e.create_system==3 for e in z.infolist())
    for p in src.iterdir():p.chmod(0o444)
    src.chmod(0o555);(root/'linux-manifest.json').write_text(json.dumps(report,indent=2));print(report['archive_sha256'])
if __name__=='__main__':main()
