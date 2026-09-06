"""Stage a separate exact-endgame candidate on released Tempest r1."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
manifest=json.loads((HERE/'table-inventory/download-manifest.json').read_text())
source=ROOT/'tempest_exact';out=HERE/'prototypes/tablebase';out.mkdir(exist_ok=False)
for p in source.iterdir():
    if p.is_file() and p.suffix in ('.py','.npz'):(out/p.name).write_bytes(p.read_bytes())
tables=out/'syzygy';tables.mkdir()
hashes={}
for name,row in manifest['files'].items():
    data=(HERE/'syzygy-data'/name).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
    (tables/name).write_bytes(data);hashes[name]=row['sha256']
s=(HERE/'syzygy_root_template.py').read_text()
s=s.replace('TABLE_HASHES = {}  # Filled with the verified payload manifest at staging.','TABLE_HASHES = '+repr(hashes))
(out/'syzygy_root.py').write_text(s,newline='\n')
p=out/'endgame_exact.py';s=p.read_text().replace('def choose_exact(board, seen=None):','def _choose_original_dtm(board, seen=None):')
s+='''

# Preserve our original mate-distance policy where it already has coverage.
from syzygy_root import choose_syzygy

def choose_exact(board, seen=None):
    original = _choose_original_dtm(board, seen)
    return original if original is not None else choose_syzygy(board, seen)
'''
p.write_text(s,newline='\n')
files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
result=dict(source='lab/tempest_edges/prototypes/tablebase',files=files,total_uncompressed_bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),
    policy='Original KQK/KRK DTM first, then our DTZ root policy for 3/4 pieces. No castling. Final 200 absolute plies use existing search. Immediate known repetition, actual fifty, mate precedence. No claim of a full-history expanded tablebase proof.',
    provenance='Lichess mirror original Syzygy data, WDL and non-rounded DTZ, published SHA256 verified. Preinstalled chess.syzygy probing. Current rules explicitly permit shipped tablebases.')
(HERE/'tablebase-manifest.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='files'}))
