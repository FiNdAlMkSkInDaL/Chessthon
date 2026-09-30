"""Read-only public contract and table-directory availability/size inventory."""
import hashlib,json,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent;out=HERE/'table-inventory';out.mkdir(exist_ok=False)
urls={
 'rules':'https://aichessathon.com/docs/rules.md',
 'contract':'https://aichessathon.com/docs/agent-contract.md',
 'sesse':'https://tablebase.sesse.net/syzygy/3-4-5/',
 'lichess':'https://tablebase.lichess.ovh/tables/standard/3-4-5/'
}
rows=[]
for name,url in urls.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AI Chessathon-research/1.0'}),timeout=15) as r:
            data=r.read(2000000);status=r.status
        (out/f'{name}.txt').write_bytes(data)
        row=dict(name=name,url=url,status=status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    except Exception as e:row=dict(name=name,url=url,error=str(e))
    rows.append(row);print(json.dumps(row),flush=True)
(out/'inventory.json').write_text(json.dumps(rows,indent=2))
