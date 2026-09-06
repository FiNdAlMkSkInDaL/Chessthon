"""Prepare an allowlisted validation transport, never a submission release."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--label', required=True)
    ap.add_argument('--source', type=Path, required=True)
    args = ap.parse_args()
    assert args.label.replace('-', '').isalnum()
    source = args.source.resolve()
    assert source.is_relative_to(ROOT) and (source / 'agent.py').is_file()
    out = ROOT / 'lab/odin/native_release' / args.label
    out.mkdir(exist_ok=False)
    names = sorted(p.name for p in source.glob('*.py'))
    hashes = {name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in names}
    incoming = out / 'incoming.zip'
    with zipfile.ZipFile(incoming, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in names:
            archive.write(source/name, name)
    files = set()
    for directory in ('lab/odin/release', 'lab/odin/history_perf', 'lab/odin/history_compact', 'lab/odin/sparse_guard', 'lab/odin/compact_guard', 'lab/odin/warmup_fix', 'lab/odin/storm_plus', 'lab/odin/official-harness-91f70e54/harness',
                      'lab/odin/native_release'):
        files.update(p for p in (ROOT/directory).glob('*.py'))
    for relative in ('lab/laptop_match.py', 'lab/laptop_runner.py', 'lab/release_audit.py',
                     'lab/paired_match_stats.py', 'lab/perft.py', 'lab/odin/odin-diagnostics.jsonl',
                     'lab/odin/test_odin_state.py', 'lab/odin/test_odin_clock.py',
                     'lab/odin/test_release_repairs.py',
                     'lab/odin/release_openings/development.fen', 'lab/odin/release_openings/holdout.fen',
                     'lab/odin/release_openings/manifest.json'):
        path = ROOT/relative
        if path.is_file():
            files.add(path)
    with zipfile.ZipFile(out/'transport.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.write(incoming, 'incoming.zip')
    manifest = {'source': source.relative_to(ROOT).as_posix(), 'label': args.label,
                'source_hashes': hashes,
                'incoming_sha256': hashlib.sha256(incoming.read_bytes()).hexdigest(),
                'transport_sha256': hashlib.sha256((out/'transport.zip').read_bytes()).hexdigest(),
                'note': 'Transport only. Final archive must be packed and tested on Linux.'}
    (out/'transport-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
