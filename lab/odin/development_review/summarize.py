import json
from pathlib import Path
import sys

rows=[json.loads(s) for s in Path(sys.argv[1]).read_text().splitlines()]
positions=[r for r in rows if r.get('type')=='position']
print('positions',len(positions))
for before,after in zip(positions,positions[1:]):
    if not before['candidate_turn']:
        continue
    sign=1 if before['turn']=='white' else -1
    drop=sign*(before['white_cp']-after['white_cp'])
    if drop<35:
        continue
    print(json.dumps({'ply':before['ply'],'move':str(before['move_number'])+'.'+before['played_san'],
                      'before':before['white_cp'],'after':after['white_cp'],'drop':drop,
                      'best_pv':before['pv_san'],'time_left_ms':before['timing']['time_left_ms'],
                      'telemetry':before['telemetry']}))
