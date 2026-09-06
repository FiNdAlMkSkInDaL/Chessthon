"""Join transparent finite-reference site diagnostics into a review artifact."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import chess

ap=argparse.ArgumentParser()
ap.add_argument('--selection',type=Path,default=HERE/'selected-roots.json')
ap.add_argument('--probes',type=Path,default=HERE/'odin-r10-probes.jsonl')
ap.add_argument('--rounds',type=int,nargs='+',default=list(range(26,30)))
ap.add_argument('--output',type=Path,default=HERE/'review-summary.json')
args=ap.parse_args()
cases=json.loads(args.selection.read_text(encoding='utf-8'))
probes=[json.loads(s) for s in args.probes.read_text(encoding='utf-8').splitlines()]
assert probes[-1].get('verdict')=='PASS'
def read(path):
    rows=[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
    assert rows[-1]['type']=='summary'
    return {r['id']:r for r in rows if r['type']=='case'}
deep={};alternatives={}
for rnd in args.rounds:
    deep.update(read(HERE/f'round-{rnd}-deep.jsonl'))
    alternatives.update(read(HERE/f'round-{rnd}-deep-odin.jsonl'))
results=[]
for c in cases:
    d=deep[c['id']];a=alternatives[c['id']]
    sign=1 if c['storm_colour']=='white' else -1
    board=chess.Board(c['fen'])
    best=d['best'];played=d['played']
    ownprobes=[r for r in probes if r.get('id')==c['id']]
    result={k:c[k] for k in ('id','round','ply','absolute_ply','fen','played_san','played_uci','time_left_ms','selection_reason')}
    result.update(best_san=board.san(chess.Move.from_uci(best['pv_uci'][0])),best_stm_cp=sign*best['white_cp'],
                  best_white_mate=best.get('white_mate'),storm_white_mate=played.get('white_mate'),
                  storm_forced_stm_cp=sign*played['white_cp'],storm_reference_loss_cp=sign*(best['white_cp']-played['white_cp']),odin=[])
    for p in ownprobes:
        ref=played if p['uci']==c['played_uci'] else a['alternatives'][p['uci']]
        result['odin'].append(dict(mode=p['mode'],san=p['san'],uci=p['uci'],depth=p['info'].get('depth'),
                                  actual_wall_ms=p['actual_wall_ms'],reference_stm_cp=sign*ref['white_cp'],
                                  white_mate=ref.get('white_mate'),
                                  improvement_over_recorded_storm_cp=None if ref.get('white_mate') is not None or played.get('white_mate') is not None else sign*(ref['white_cp']-played['white_cp'])))
    results.append(result)
args.output.write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
print(json.dumps([{k:r[k] for k in ('id','played_san','best_san','best_stm_cp','storm_forced_stm_cp','odin')} for r in results],indent=2))
