"""Inventory verified mirror manifests before downloading any table payload."""
import hashlib,json,re,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent;out=HERE/'table-inventory'
base='https://tablebase.lichess.ovh/tables/standard/'
for name in ('bytes.tsv','sha256','3-4-5-wdl/','3-4-5-dtz/','3-4-5-dtz-nr/'):
    with urllib.request.urlopen(base+name,timeout=15) as r:data=r.read(2000000)
    (out/('mirror-'+name.replace('/','')+'.txt')).write_bytes(data)
rows=[]
for sub,suffix in [('3-4-5-wdl','rtbw'),('3-4-5-dtz','rtbz'),('3-4-5-dtz-nr','rtbz')]:
    text=(out/f'mirror-{sub}.txt').read_text()
    for line in text.splitlines():
        m=re.search(r'href="([KQRBNPv]+\.'+suffix+r')".*?\s(\d+)\s*$',line)
        if m and len(m[1].split('.')[0].replace('v',''))<=4:rows.append(dict(directory=sub,name=m[1],bytes=int(m[2]),url=base+sub+'/'+m[1]))
result=dict(files=rows,totals={sub:sum(r['bytes'] for r in rows if r['directory']==sub) for sub in ('3-4-5-wdl','3-4-5-dtz','3-4-5-dtz-nr')},scope='All 3/4-piece files in public listings. Payloads not downloaded yet. Known SHA256 manifest retained.')
(out/'sizes.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='files'}))
