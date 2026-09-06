"""Follow the public mirror roots, retaining responses and transport errors."""
import hashlib,json,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent;out=HERE/'table-inventory'
rows=[]
for name,url in [('sesse-http','http://tablebase.sesse.net/syzygy/3-4-5/'),('lichess-root','https://tablebase.lichess.ovh/tables/')]:
    try:
        with urllib.request.urlopen(url,timeout=15) as r:data=r.read(2000000);status=r.status
        (out/f'{name}.txt').write_bytes(data)
        row=dict(name=name,url=url,status=status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    except Exception as e:row=dict(name=name,url=url,error=str(e))
    rows.append(row);print(json.dumps(row),flush=True)
(out/'more.json').write_text(json.dumps(rows,indent=2))
