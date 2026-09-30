"""New9-pair generation screen and24-pair deeper confirmation families."""
import json,hashlib,sys,os
from pathlib import Path
import chess,chess.engine
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from lab.odin.new_games.review_new import reference
from lab.odin.release_openings.build import known_positions,bkey
from lab.odin.development_review.review import pin_cpu4
pin_cpu4(os.getpid(),8)
paths=[ROOT/f'lab/odin/release_openings/{x}.jsonl' for x in ('development','holdout')]+[HERE/f'{x}-openings/openings.jsonl' for x in ('screen','overnight')]
used={r['opening_position_key'] for p in paths for r in [json.loads(s) for s in p.read_text().splitlines()]}
known,_=known_positions();pool=[json.loads(s) for s in (ROOT/'lab/odin/release_openings/candidate-pool.jsonl').read_text().splitlines()]
pool=sorted(pool,key=lambda r:hashlib.sha256(('odin-generation-'+r['id']).encode()).hexdigest())
out=HERE/'generation-openings';out.mkdir(exist_ok=False)
exe='stockfish'
with chess.engine.SimpleEngine.popen_uci(exe) as engine,(out/'reference.jsonl').open('x') as log:
    engine.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
    for split,n in [('screen',3),('confirm',8)]:
        selected=[];counts={g:0 for g in ('e4','d4','flank')}
        for row in pool:
            if row['opening_position_key'] in used or counts[row['group']]>=n:continue
            b=chess.Board(row['fen'])
            if bkey(b) in known:continue
            ref=reference(engine,b,100000);ok=abs(ref['white_cp'])<=80 and ref.get('white_mate') is None
            log.write(json.dumps({'split':split,'id':row['id'],'accepted':ok,'reference':ref})+'\n');log.flush()
            if ok:used.add(row['opening_position_key']);selected.append(row);counts[row['group']]+=1
            if all(c==n for c in counts.values()):break
        assert all(c==n for c in counts.values())
        (out/f'{split}.fen').write_text('\n'.join(r['fen'] for r in selected)+'\n',newline='\n')
        (out/f'{split}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected))
        print(json.dumps({'split':split,'positions':len(selected),'sha256':hashlib.sha256((out/f'{split}.fen').read_bytes()).hexdigest()}),flush=True)
