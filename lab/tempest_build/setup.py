"""Isolate the v6-derived fallback and pin current public contract evidence."""
import hashlib, io, json, tarfile, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
COMMIT = '284724ab56cecb2a1a9a4e5769b4748adab4ed90'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    target = ROOT / 'tempest'
    target.mkdir(exist_ok=False)
    original = {p.name: sha(p) for p in sorted((ROOT / 'odin_v6').glob('*.py'))}
    assert len(original) == 12
    for name in original:
        (target / name).write_bytes((ROOT / 'odin_v6' / name).read_bytes())
    core = target / 'core_nb.py'
    text = core.read_text()
    begin = text.index('    """Whether the current position is claimable')
    end = text.index('\n\n\n@njit', begin)
    text = text[:begin] + '''    """Actual fifty moves; callers establish mate/stalemate precedence first."""
    return nlegal > 0 and np.int32(st[FIFTY]) >= 100''' + text[end:]
    assert text.count('np.int32(st[FIFTY]) >= 99') == 4
    text = text.replace('np.int32(st[FIFTY]) >= 99', 'np.int32(st[FIFTY]) >= 100')
    core.write_text(text, encoding='utf-8', newline='\n')
    public = HERE / 'public'; public.mkdir(exist_ok=True)
    downloads = []
    for name, url in [('agent-contract.md', 'https://aichessathon.com/docs/agent-contract.md'),
                      ('rules.md', 'https://aichessathon.com/docs/rules.md'),
                      ('starter.tar.gz', f'https://codeload.github.com/advitrocks9/aichessathon-starter/tar.gz/{COMMIT}')]:
        data = urllib.request.urlopen(url, timeout=45).read()
        path = public / name; path.write_bytes(data)
        downloads.append(dict(url=url, path=str(path.relative_to(ROOT)), sha256=sha(path),
                              fetched_utc=datetime.now(timezone.utc).isoformat()))
    harness = HERE / ('official-' + COMMIT[:8])
    harness.mkdir(exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO((public/'starter.tar.gz').read_bytes())) as archive:
        for member in archive.getmembers():
            parts = Path(member.name).parts[1:]
            if not parts or parts[0] != 'harness' or not member.isfile(): continue
            destination = (harness.joinpath(*parts)).resolve()
            assert destination.is_relative_to(harness.resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.extractfile(member).read())
    referee = (harness/'harness/referee.py').read_text()
    assert 'finish = board.outcome()' in referee and 'board.is_repetition(3)' in referee
    assert 'board.is_fifty_moves()' in referee
    record = dict(baseline=original, fallback={p.name:sha(p) for p in target.glob('*.py')},
                  commit=COMMIT, downloads=downloads, baseline_unchanged=all(sha(ROOT/'odin_v6'/n)==h for n,h in original.items()))
    (HERE/'setup-manifest.json').write_text(json.dumps(record, indent=2))
    print(json.dumps(record))

if __name__ == '__main__': main()
