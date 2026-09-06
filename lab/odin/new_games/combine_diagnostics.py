import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
rows=json.loads((HERE/'selected-roots.json').read_text(encoding='utf-8'))+json.loads((HERE/'selected-round30.json').read_text(encoding='utf-8'))
assert len(rows)==20 and len({r['id'] for r in rows})==20
assert all(not r['holdout_position_overlap'] for r in rows)
out=HERE/'native-diagnostic-roots.json'
assert not out.exists()
out.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'cases':len(rows),'purpose':'Extra Linux diagnostics after lane a completes; no release candidate changes.'}))
