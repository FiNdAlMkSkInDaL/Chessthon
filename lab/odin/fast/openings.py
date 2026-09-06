"""Fresh candidate-blind families for short screens and56 overnight pairs."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from lab.odin.release_openings.build import known_positions,bkey
from lab.odin.new_games.review_new import reference
from lab.odin.development_review.review import pin_cpu4
import chess,chess.engine
ap=argparse.ArgumentParser();ap.add_argument('--split',choices=('screen','overnight'),required=True);ap.add_argument('--cpu',type=int,required=True);args=ap.parse_args()
pin_cpu4(os.getpid(),args.cpu)
old=ROOT/'lab/odin/release_openings'
used=[json.loads(s) for f in ('development.jsonl','holdout.jsonl') for s in (old/f).read_text(encoding='utf-8').splitlines()]
families={r['opening_position_key'] for r in used}
known,_=known_positions()
pool=[json.loads(s) for s in (old/'candidate-pool.jsonl').read_text(encoding='utf-8').splitlines()]
pool=[r for r in pool if r['opening_position_key'] not in families and bkey(chess.Board(r['fen'])) not in known]
def order(r):return hashlib.sha256(('odin-v6-20260905-'+r['id']).encode()).hexdigest()
pool=sorted(pool,key=order)
pool=[r for r in pool if ('screen' if int(order(r),16)%4==0 else 'overnight')==args.split]
quota={'e4':8,'d4':8,'flank':8} if args.split=='screen' else {'e4':20,'d4':20,'flank':16}
counts={k:0 for k in quota};selected=[]
exe=Path('C:/Users/finla/AppData/Local/ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe')
out=HERE/f'{args.split}-openings';out.mkdir(exist_ok=False)
with chess.engine.SimpleEngine.popen_uci(str(exe)) as engine,(out/'reference.jsonl').open('x',encoding='utf-8') as log:
    engine.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
    for r in pool:
        group=r['group']
        if counts[group]>=quota[group]:continue
        ref=reference(engine,chess.Board(r['fen']),100000)
        accepted=abs(ref['white_cp'])<=80 and ref.get('white_mate') is None
        log.write(json.dumps({'id':r['id'],'accepted':accepted,'reference':ref})+'\n');log.flush()
        if accepted:selected.append(r);counts[group]+=1
        if counts==quota:break
assert counts==quota
(out/'openings.fen').write_text('\n'.join(r['fen'] for r in selected)+'\n',encoding='utf-8')
(out/'openings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected),encoding='utf-8')
manifest={'split':args.split,'positions':len(selected),'counts':counts,'node_cap':100000,'maximum_abs_reference_cp':80,
          'pool_sha256':hashlib.sha256((old/'candidate-pool.jsonl').read_bytes()).hexdigest(),
          'fen_sha256':hashlib.sha256((out/'openings.fen').read_bytes()).hexdigest(),
          'selection':'New hash-split opening families, excluding all previous48 selected families, training exclusions inherited from audited pool, and all known site positions. Candidate blind.'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest),flush=True)
