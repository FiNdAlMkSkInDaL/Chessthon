"""Allowlisted transport for the exact-endgame candidate and native gate."""
from pathlib import Path
import io,zipfile,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
out=ROOT/'lab/odin/native_release/tempest-exact-r1';out.mkdir(exist_ok=False)
source=ROOT/'tempest_exact';expected={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
assert len(expected)==14
incoming=io.BytesIO()
with zipfile.ZipFile(incoming,'w',zipfile.ZIP_DEFLATED) as z:
    for name in sorted(expected):z.write(source/name,name)
gate=(ROOT/'lab/odin/release/native_gate.py').read_text()
needle="('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',1000)"
assert gate.count(needle)==1
gate=gate.replace(needle,needle+",\n                                  ('7k/8/5KQ1/8/8/8/8/8 w - - 99 50',100),\n                                  ('7k/8/8/8/8/8/8/KR6 w - - 0 1',100)")
with zipfile.ZipFile(out/'transport.zip','x',zipfile.ZIP_DEFLATED) as dest,zipfile.ZipFile(ROOT/'lab/odin/native_release/tempest-rules-r1/transport.zip') as old:
    for name in old.namelist():
        if name in ('incoming.zip','lab/odin/release/native_gate.py'):continue
        dest.writestr(name,old.read(name))
    dest.writestr('incoming.zip',incoming.getvalue());dest.writestr('exact-source-manifest.json',json.dumps(expected))
    dest.writestr('lab/odin/release/native_gate.py',gate)
    dest.write(HERE/'pack_exact_linux.py','lab/tempest_build/pack_exact_linux.py')
(out/'transport-manifest.json').write_text(json.dumps(dict(source=expected,transport_sha256=hashlib.sha256((out/'transport.zip').read_bytes()).hexdigest(),native_gate_sha256=hashlib.sha256(gate.encode()).hexdigest(),scope='Adds two exact-endgame protocol positions; no historical harness or frozen gate changed.'),indent=2))
print('exact transport ready')
