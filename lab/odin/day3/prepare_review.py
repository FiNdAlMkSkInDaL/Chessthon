"""Freeze Day3 critical-root diagnostics after the independent 100k scan."""
import json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
selected={31:[81],32:[8,18],33:[4,6,34],34:[23,25]}
out=[]
for rnd,plies in selected.items():
    path=HERE/'reference'/f'round-{rnd}-screen.jsonl'
    rows=[json.loads(s) for s in path.read_text().splitlines()]
    assert rows[-1]['type']=='summary'
    for r in rows:
        if r.get('type')=='position' and r['ply'] in plies:
            assert r['storm_turn']
            out.append({'id':f'day3-r{rnd}-p{r["ply"]}',**r,'screen_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
assert len(out)==8
(HERE/'selected-roots.json').write_text(json.dumps(out,indent=2)+'\n')
print('Frozen eight diagnostic roots, separate from completed overnight strength evidence.')
