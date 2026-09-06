"""Read-only postgame Syzygy reference; never part of a submission or training.

One request/second, retained complete responses, no automatic HTTP retries.
"""
import json,time,urllib.request,urllib.parse,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent/'round38'
rows=json.loads((HERE/'five-piece-positions.json').read_text())
with (HERE/'tablebase-review.jsonl').open('x') as f:
    def emit(r):f.write(json.dumps(r)+'\n');f.flush()
    emit(dict(type='metadata',source='https://github.com/lichess-org/lila-tablebase',script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Offline postgame diagnostics only; not shipped. API category is side-to-move oriented; full game repetition remains a separate constraint.'))
    first=json.loads((HERE/'first-five-piece-tablebase.json').read_text())
    for i,r in enumerate(rows):
        url='https://tablebase.lichess.ovh/standard?'+urllib.parse.urlencode({'fen':r['fen']})
        if i==0:data=first['response']
        else:
            time.sleep(1)
            with urllib.request.urlopen(url,timeout=20) as response:data=json.load(response)
        emit(dict(type='position',**r,url=url,response=data))
        if i%20==0:print(i,r['ply'],data['category'],flush=True)
    emit(dict(type='complete',positions=len(rows)))
