"""Pack allowlisted incoming source on Linux and bind every member byte."""
from pathlib import Path
import json
import platform
import sys
import zipfile


def main():
    assert sys.platform == 'linux' and platform.machine() == 'x86_64'
    assert sys.version_info[:2] == (3, 12)
    root = Path.cwd().resolve()
    sys.path.insert(0, str(root))
    from lab.release_audit import audit
    incoming = audit(root/'incoming.zip')
    assert all('/' not in entry['name'] and entry['name'].endswith('.py')
               for entry in incoming['entries'])
    source = root/'source'
    source.mkdir()
    with zipfile.ZipFile(root/'incoming.zip') as archive:
        for entry in incoming['entries']:
            (source/entry['name']).write_bytes(archive.read(entry['name']))
    final = root/'candidate-linux-x86.zip'
    with zipfile.ZipFile(final, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for entry in incoming['entries']:
            archive.write(source/entry['name'], entry['name'])
    report = audit(final)
    assert [(e['name'], e['sha256']) for e in incoming['entries']] == [
        (e['name'], e['sha256']) for e in report['entries']]
    with zipfile.ZipFile(final) as archive:
        assert all(e.create_system == 3 for e in archive.infolist())
    for path in source.iterdir():
        path.chmod(0o444)
    source.chmod(0o555)
    (root/'linux-manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'event': 'LINUX_SOURCE_IDENTITY_PASS', 'sha256': report['archive_sha256'],
                      'members': len(report['entries'])}), flush=True)


if __name__ == '__main__':
    main()
