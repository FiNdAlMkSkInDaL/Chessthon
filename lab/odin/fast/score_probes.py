"""Independent finite reference comparison of changed native diagnostic choices."""
import json,os,sys,hashlib
from pathlib import Path
import chess,chess.engine
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from lab.odin.new_games.review_new import reference
from lab.odin.development_review.review import pin_cpu4
pin_cpu4(os.getpid(),8)
cases={r['id']:r for r in json.loads((ROOT/'lab/odin/new_games/native-diagnostic-roots.json').read_text())}
data={}
for label in ('baseline','selective'):
    rows=[json.loads(s) for s in (HERE/f'probe-{label}.jsonl').read_text().splitlines()]
    assert rows[-1]['type']=='summary' and rows[-1]['verdict']=='PASS'
    data[label]={(r['id'],r['mode']):r for r in rows if r['type']=='probe'}
exe=Path('stockfish')
records=[];cache={}
with chess.engine.SimpleEngine.popen_uci(str(exe)) as engine,(HERE/'diagnostic-reference.jsonl').open('x') as log:
    engine.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
    for key,a in data['baseline'].items():
        b=data['selective'][key];case=cases[key[0]]
        row={'id':key[0],'mode':key[1],'baseline':a['san'],'candidate':b['san'],'baseline_depth':a['info']['depth'],'candidate_depth':b['info']['depth'],'changed':a['uci']!=b['uci']}
        if row['changed']:
            board=chess.Board(case['start_fen'])
            for uci in case['history_uci']:board.push_uci(uci)
            assert board.fen()==case['fen']
            scores=[]
            for r in (a,b):
                ckey=(key[0],r['uci'])
                if ckey not in cache:cache[ckey]=reference(engine,board,2000000,[chess.Move.from_uci(r['uci'])])
                ref=cache[ckey];scores.append(ref['white_cp']*(1 if board.turn else -1))
            row.update(baseline_reference_cp=scores[0],candidate_reference_cp=scores[1],difference_cp=scores[1]-scores[0])
        else:row['difference_cp']=0
        records.append(row);log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
result={'scope':'Known development roots, finite Stockfish19 forced-move references. No confidence or strength estimate.',
        'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'probe-baseline.jsonl',HERE/'probe-selective.jsonl')},
        'rows':records,'adaptive_mean_difference_cp':sum(r['difference_cp'] for r in records if r['mode']=='adaptive')/20}
(HERE/'diagnostic-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
