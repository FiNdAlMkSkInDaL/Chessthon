"""Download only enumerated 3/4-piece WDL and unrounded DTZ, verify known SHA256."""
import hashlib,json,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent;inventory=HERE/'table-inventory'
sizes=json.loads((inventory/'sizes.json').read_text())
url='https://tablebase.lichess.ovh/tables/standard/3-4-5-dtz-nr/3-4-5-dtz-nr.sha256'
with urllib.request.urlopen(url,timeout=15) as r:data=r.read(1000000)
(inventory/'nr-sha256.txt').write_bytes(data)
def parse(text):
    result={}
    for line in text.splitlines():
        digest,name=line.split(maxsplit=1);result[Path(name.strip().lstrip('*')).name]=digest
    return result
known={'3-4-5-wdl':parse((inventory/'mirror-sha256.txt').read_text()),'3-4-5-dtz-nr':parse(data.decode())}
rows=[r for r in sizes['files'] if r['directory'] in known]
assert sum(r['bytes'] for r in rows)<5000000
out=HERE/'syzygy-data';out.mkdir(exist_ok=False);manifest={}
for row in rows:
    expected=known[row['directory']][row['name']]
    with urllib.request.urlopen(row['url'],timeout=30) as r:blob=r.read(5000001)
    assert len(blob)==row['bytes'] and hashlib.sha256(blob).hexdigest()==expected,row['name']
    (out/row['name']).write_bytes(blob);manifest[row['name']]=dict(bytes=len(blob),sha256=expected,url=row['url'])
result=dict(files=manifest,total_bytes=sum(r['bytes'] for r in manifest.values()),checksums='Published Lichess standard SHA256 and 3-4-5-dtz-nr.sha256; HTTPS verified',dtz='Non-rounded DTZ tables; file payloads checked against dedicated nr manifest')
(inventory/'download-manifest.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(files=len(manifest),total_bytes=result['total_bytes'])))
