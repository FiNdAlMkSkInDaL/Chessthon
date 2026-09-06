"""Prepare audited source transports; final upload archives are packed on Linux."""
import io,hashlib,json,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];out=HERE/'native';out.mkdir(exist_ok=False)
names=('tables_guard','capture_tables');manifest=json.loads((HERE/'bundle-manifest.json').read_text())
payload={}
for name in names:
    source=HERE/'prototypes'/name;expected=manifest['files'][name];d=out/name;d.mkdir()
    incoming=io.BytesIO()
    with zipfile.ZipFile(incoming,'w',zipfile.ZIP_DEFLATED) as z:
        for file,digest in expected.items():
            data=(source/file).read_bytes();assert hashlib.sha256(data).hexdigest()==digest;z.writestr(file,data)
    payload[f'native/{name}/incoming.zip']=incoming.getvalue();payload[f'native/{name}/source-manifest.json']=json.dumps(expected).encode()
    (d/'source-manifest.json').write_text(json.dumps(expected,indent=2))
tools=['lab/laptop_match.py','lab/laptop_runner.py','lab/release_audit.py','lab/paired_match_stats.py','lab/perft.py','lab/odin/release/__init__.py','lab/odin/release/linux_match.py','lab/odin/release/plan.py','lab/odin/release/validate_match.py']
for file in tools:payload[file]=(ROOT/file).read_bytes()
for p in (ROOT/'lab/tempest_build/official-284724ab/harness').glob('*.py'):payload[p.relative_to(ROOT).as_posix()]=p.read_bytes()
gate=(ROOT/'lab/odin/release/native_gate.py').read_text()
needle="('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',1000)";assert gate.count(needle)==1
gate=gate.replace(needle,needle+",\n                                  ('8/k1P5/2K5/8/8/8/8/8 w - - 0 1',1200),\n                                  ('8/k1P5/2K5/8/8/8/8/8 w - - 0 1',1199),\n                                  ('8/8/8/8/8/3K4/2BN4/k7 w - - 0 1',1200)")
anchor="                    assert chess.Move.from_uci(uci) in chess.Board(fen).legal_moves"
assert gate.count(anchor)==1
gate=gate.replace(anchor,anchor+"\n                    if fen == '8/k1P5/2K5/8/8/8/8/8 w - - 0 1' and clock == 1200:\n                        assert uci == 'c7c8r', ('Underpromotion avoids stalemate',uci)")
payload['lab/odin/release/native_gate.py']=gate.encode()
payload['lab/tempest_edges/pack_linux.py']=(HERE/'pack_linux.py').read_bytes()
baseline=ROOT/'lab/odin/native_release/tempest-exact-r1/candidate-linux-x86.zip'
assert hashlib.sha256(baseline.read_bytes()).hexdigest()=='0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4'
payload['baseline-tempest-r1.zip']=baseline.read_bytes()
payload['development.fen']=(ROOT/'lab/odin/release_openings/development.fen').read_bytes()
with zipfile.ZipFile(out/'transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    for name,data in payload.items():z.writestr(name,data)
report=dict(entries={name:hashlib.sha256(data).hexdigest() for name,data in payload.items()},transport_sha256=hashlib.sha256((out/'transport.zip').read_bytes()).hexdigest(),scope='Transport only; no release promotion. Untouched current referee and runner included; isolated gate adds table/panic protocol cases.')
(out/'transport-manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(entries=len(payload),transport_sha256=report['transport_sha256'])))
