"""Fixed-node source comparison and legal search-state collection."""
import os,sys,argparse,hashlib,inspect,json,time
from pathlib import Path
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--limit',type=int,default=0);ap.add_argument('--cpu',type=int,default=8);ap.add_argument('--nodes',type=int,default=20000);a=ap.parse_args()
from lab.laptop_runner import apply_windows_affinity
if os.name=='nt':assert apply_windows_affinity(a.cpu)['applied']
else:os.sched_setaffinity(0,{a.cpu})
import numpy as np,chess
sys.path.insert(0,str(a.source.resolve()));began=time.perf_counter();import agent,core_nb as c
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert c.NUMBA_READY and c.root_search_nb.nopython_signatures
signatures=list(map(str,c.root_search_nb.nopython_signatures));cold=time.perf_counter()-began
source=inspect.getsource(c.search_root)
for old,new in [('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0'),('max_nodes = 10**15  # deadline inside compiled search is authoritative',f'max_nodes = {a.nodes}')]:
    assert source.count(old)==1;source=source.replace(old,new)
exec(compile(source,'<tempest-fixed-node-sampler-driver>','exec'),c.__dict__)
rows=[json.loads(s) for s in (HERE/'data/roots.jsonl').read_text().splitlines()]
if a.limit:rows=rows[:a.limit]
def clear():
    for name in ('TT_KEY','TT_MOVE','TT_SCORE','TT_DEPTH','TT_GEN','TT_AGE','KILLERS','HISTORY'):getattr(c,name).fill(0)
def run(r):
    clear();b=chess.Board(r['start_fen']);z=[]
    for u in r['history_uci']:
        z.append(from_fen(b.fen()).key);b.push_uci(u)
    assert b.fen()==r['fen'];p=from_fen(b.fen());z.append(p.key)
    m=c.search_root(p,generate_legal(p),1e12,1e12,False,z)
    assert chess.Move.from_uci(move_uci(m)) in b.legal_moves
    info=c.last_info();result=dict(id=r['id'],uci=move_uci(m),score=info['score'],depth=info['depth'],nodes=info['nodes'])
    samples=[]
    if hasattr(c,'_LAB_SAMPLES'):
        data=c._LAB_SAMPLES;seen=set();count={'quiet':0,'guard':0}
        for slot in range(c.SAMPLE_SLOTS):
            base=c.SAMPLE_BASE+slot*c.SAMPLE_WIDTH;ply=int(data[base]);node=int(data[base+2])
            if not node:continue
            child=b.copy();path=[]
            for packed in data[base+15:base+15+ply]:
                u=move_uci(int(packed));assert chess.Move.from_uci(u) in child.legal_moves,(r['id'],path,u)
                path.append(u);child.push_uci(u)
            bb,_,st=c.pack_pos(from_fen(child.fen()))
            expected=np.array(data[base+3:base+15],np.int64).view(np.uint64)
            assert np.array_equal(bb,expected),(r['id'],path)
            assert c.evaluate_nb(bb,st,False)==data[base+1]
            if child.is_game_over() or child.is_repetition(3) or child.is_fifty_moves():continue
            noisy=child.is_check() or any(child.is_capture(m) or m.promotion for m in child.legal_moves)
            kind='guard' if noisy or slot>=32 else 'quiet'
            k=' '.join(child.fen(en_passant='legal').split()[:4])
            if k in seen or count[kind]>=(8 if kind=='quiet' else 2):continue
            seen.add(k);count[kind]+=1
            samples.append(dict(id=hashlib.sha256((r['id']+child.fen()).encode()).hexdigest()[:24],root_id=r['id'],fen=child.fen(),start_fen=r['start_fen'],history_uci=r['history_uci']+path,path_uci=path,family=r['family'],source_game=r['source_game'],split=r['split'],kind=kind,static_white_cp=int(data[base+1])*(1 if child.turn else -1),observation='static evaluation at a visited search state; no root bound implied',sampling=dict(reservoir_class='stand' if slot<32 else 'static_guard',seen=int(data[2 if slot<32 else 3]),capacity=32 if slot<32 else 8,per_root_cap=8 if kind=='quiet' else 2)))
    assert list(map(str,c.root_search_nb.nopython_signatures))==signatures
    return result,samples
a.output.parent.mkdir(exist_ok=True,parents=True)
with a.output.open('x') as out:
    def emit(r):out.write(json.dumps(r)+'\n');out.flush()
    emit(dict(type='metadata',cold_seconds=cold,source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.source.glob('*.py')},driver_sha256=hashlib.sha256(source.encode()).hexdigest(),roots_sha256=hashlib.sha256((HERE/'data/roots.jsonl').read_bytes()).hexdigest(),nodes=a.nodes,roots=len(rows)))
    x,sx=run(rows[0]);run(rows[-1]);y,sy=run(rows[0]);assert x==y and sx==sy
    emit(dict(type='isolation',pass_ABA=True))
    for i,r in enumerate(rows):
        result,samples=run(r);emit(dict(type='root',**result,samples=samples))
        if i%100==0:print(i,len(samples),flush=True)
    emit(dict(type='complete',roots=len(rows),seconds=time.perf_counter()-began))
