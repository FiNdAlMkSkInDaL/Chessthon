"""Stage a qualified research candidate for Linux packing and exact-archive gates."""
import argparse, hashlib, io, json, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True);args=ap.parse_args()
assert args.variant.replace('-','').isalnum()
source=HERE/'native'/args.variant
meta=json.loads((HERE/'native'/f'{args.variant}.json').read_text())
expected=meta['files'];assert len(expected)==15
assert set(expected)=={p.name for p in source.iterdir() if p.suffix in ('.py','.npz')}
assert set(expected)-{n for n in expected if n.endswith('.py')}=={'value.npz','three_piece_dtm.npz'}
assert all(hashlib.sha256((source/n).read_bytes()).hexdigest()==h for n,h in expected.items())
out=HERE/'release-gates'/args.variant;out.mkdir(parents=True,exist_ok=False)
incoming=io.BytesIO()
with zipfile.ZipFile(incoming,'w',zipfile.ZIP_DEFLATED) as z:
    for name in sorted(expected):z.write(source/name,name)
desktop=ROOT.parent/'agent.zip'
assert hashlib.sha256(desktop.read_bytes()).hexdigest()=='0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4'
files=set((ROOT/'lab/odin/release').glob('*.py'))
files.update((ROOT/'lab/tempest_build/official-284724ab/harness').glob('*.py'))
files.update(ROOT/p for p in ('lab/laptop_match.py','lab/laptop_runner.py','lab/release_audit.py','lab/paired_match_stats.py','lab/perft.py'))
files.add(HERE/'pack_linux.py')
with zipfile.ZipFile(out/'transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(files):z.write(p,p.relative_to(ROOT).as_posix())
    z.writestr('incoming.zip',incoming.getvalue())
    z.writestr('source-manifest.json',json.dumps(expected))
    z.write(desktop,'baseline-tempest.zip')
(out/'manifest.json').write_text(json.dumps(dict(variant=args.variant,files=expected,transport_sha256=hashlib.sha256((out/'transport.zip').read_bytes()).hexdigest(),purpose='Exact-source Linux pack/protocol gate. No confirmation openings included and no Desktop promotion.'),indent=2))
print(str(out))
