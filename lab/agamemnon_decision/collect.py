"""Original forced-alternative search + exact backed-up leaves + offline teacher."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,json,sys,time,hashlib
from pathlib import Path
import numpy as np,chess,chess.engine
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity
ap=argparse.ArgumentParser();ap.add_argument('--lane',type=int,required=True);ap.add_argument('--lanes',type=int,default=4);ap.add_argument('--cpu',type=int,required=True);ap.add_argument('--phase',choices=('pilot','expand'),default='pilot');a=ap.parse_args();assert apply_windows_affinity(a.cpu)['applied']
sys.path.insert(0,str(HERE/'collector'));start=time.perf_counter()
import agent,core_nb as c
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert c.NUMBA_READY and c.root_search_nb.nopython_signatures
snapshot={k:v.copy() for k,v in vars(c).items() if isinstance(v,np.ndarray) and v.flags.writeable}
roots=[json.loads(l) for l in (HERE/'data/roots.jsonl').read_text().splitlines()]
tr=[r for r in roots if r['split']==0];dev=[r for r in roots if r['split']==1];pilot={r['id'] for r in tr[:128]+dev[:32]}
roots=[r for r in roots if (r['id'] in pilot)==(a.phase=='pilot')][a.lane::a.lanes]
dest=HERE/a.phase;dest.mkdir(exist_ok=True);outpath=dest/f'lane{a.lane}.jsonl';done=set()
if outpath.exists():
    old=[json.loads(l) for l in outpath.read_text().splitlines()]
    if old and old[-1].get('type')=='complete':print('already complete');sys.exit(0)
    done={r['id'] for r in old if r.get('type')=='root'}
EXE=Path('C:/Users/finla/AppData/Local/ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe');teacher_hash=hashlib.sha256(EXE.read_bytes()).hexdigest()
def board(r):
    b=chess.Board(r['start_fen'])
    for u in r['history_uci']:b.push_uci(u)
    assert b.fen()==r['fen'];return b
def search(b,forced=None,enabled=True):
    for k,v in snapshot.items():np.copyto(getattr(c,k),v)
    c.NN_ACC[2,0]=int(enabled);pos=from_fen(b.fen());bb,mb,st=c.pack_pos(pos);moves=generate_legal(pos)
    if forced:moves=[m for m in moves if move_uci(m)==forced]
    histboard=b.root();keys=[]
    for m in b.move_stack:keys.append(from_fen(histboard.fen()).key);histboard.push(m)
    hlen=len(keys);hist=np.zeros(hlen+c.MAX_PLY+8,np.uint64);hist[:hlen]=keys;root=np.array(moves,np.int32)
    undos=np.zeros((c.MAX_PLY,7),np.uint64);stacks=np.zeros((c.MAX_PLY,c.MAX_MOVES),np.int32);scratch=np.zeros_like(stacks);nodes=np.zeros(2,np.int64);aborted=np.zeros(1,np.int32)
    saved=None
    for depth in (5,4,3):
        for k,v in snapshot.items():np.copyto(getattr(c,k),v)
        c.NN_ACC[2,0]=int(enabled);nodes[:]=0;aborted[:]=0
        move,score=c.root_search_nb(bb,mb,st,root,len(root),depth,hist,hlen,0,-c.INF,c.INF,False,max(0,600-b.ply()),100000,undos,stacks,scratch,c.TT_KEY,c.TT_MOVE,c.TT_SCORE,c.TT_DEPTH,c.TT_GEN,c.TT_AGE,c.KILLERS,c.HISTORY,c.NET,c.NN_LAST_BB,c.NN_ACC,nodes,aborted)
        if not aborted[0]:saved=(int(move),int(score),depth,int(nodes[0]),c.NN_ACC[3:7].copy());break
    assert saved is not None
    move,score,depth,nodes,trace=saved;res=dict(uci=move_uci(move),score=score,depth=depth,nodes=nodes,bound='exact_full_window',provenance=False)
    if enabled and trace[0,30]:
        pv=[move_uci(int(trace[1+i//32,i%32])) for i in range(int(trace[0,31]))];leaf=b.copy()
        for u in pv:leaf.push_uci(u)
        assert pv and pv[0]==res['uci']
        for pt in range(12):assert int(leaf.pieces_mask(pt%6+1,pt<6))==((int(trace[0,2*pt])&0xffffffff)|((int(trace[0,2*pt+1])&0xffffffff)<<32))
        assert (0 if leaf.turn else 1)==int(trace[0,24]) and leaf.halfmove_clock==int(trace[0,27]) and leaf.fullmove_number==int(trace[0,28])
        assert score==int(trace[0,29])*(-1 if len(pv)%2 else 1),(score,trace[0,29],pv)
        pbb,pmb,pst=c.pack_pos(from_fen(leaf.fen()));value=int(c.evaluate_nb(pbb,pst,False,c.NET,c.NN_LAST_BB,c.NN_ACC));assert value==int(trace[0,29])
        hand=c.positional_correction_nb(pbb,pst);base=c.pesto_nb(pbb,pst,True)*(1 if leaf.turn else -1)
        quiet=not leaf.is_check() and not any(leaf.is_capture(m) or m.promotion for m in leaf.legal_moves)
        res.update(provenance=True,pv=pv,leaf_fen=leaf.fen(),leaf_value_white=value*(1 if leaf.turn else -1),hybrid_base_white=base+.5*hand,hybrid_base_schema='white-v2',quiet=quiet)
    return res
def analyze(engine,b,nodes,forced=None,multipv=None):
    engine.configure({'Clear Hash':None});latest={}
    with engine.analysis(b,chess.engine.Limit(nodes=nodes),root_moves=[chess.Move.from_uci(forced)] if forced else None,multipv=multipv,game=object()) as analysis:
        for fresh in analysis:
            if fresh.get('score') is not None and fresh.get('pv') and not fresh.get('lowerbound') and not fresh.get('upperbound'):latest[fresh.get('multipv',1)]=dict(fresh)
    answer=[]
    for rank,r in sorted(latest.items()):
        score=r['score'].white();answer.append(dict(uci=r['pv'][0].uci(),pv=[m.uci() for m in r['pv']],white_cp=score.score(),white_mate=score.mate(),nodes=r['nodes'],depth=r['depth'],bound='unbounded_completed_iteration'))
    assert answer
    if forced:assert answer[0]['uci']==forced
    return answer
with outpath.open('a') as f,chess.engine.SimpleEngine.popen_uci(str(EXE)) as engine:
    engine.configure({'Threads':1,'Hash':32})
    if not done:f.write(json.dumps(dict(type='metadata',teacher_sha256=teacher_hash,collector=json.loads((HERE/'collector-manifest.json').read_text()),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cold_seconds=time.perf_counter()-start,phase=a.phase,scope='Original hybrid fixed-depth selective search, fresh TT per alternative; full-window completed scores with exact propagated leaf provenance. Not a competition-clock match.'))+'\n');f.flush()
    for i,r in enumerate(roots):
        if r['id'] in done:continue
        b=board(r);own=search(b)
        if i<2:
            off=search(b,enabled=False);assert all(own[k]==off[k] for k in ('uci','score','depth','nodes'))
        teachers=analyze(engine,b,64000,multipv=3);legal=sorted(m.uci() for m in b.legal_moves);randommove=legal[int(r['id'][:8],16)%len(legal)]
        selected=list(dict.fromkeys([own['uci'],*[m['uci'] for m in teachers],r.get('played'),randommove]));selected=[u for u in selected if u in legal]
        alternatives=[]
        for u in selected:
            ownalt=search(b,u);reference=analyze(engine,b,32000,forced=u)[0];alternatives.append(dict(own=ownalt,reference=reference))
        record=dict(type='root',**r,own_root=own,teacher_top=teachers,alternatives=alternatives)
        f.write(json.dumps(record)+'\n');f.flush()
        if i%20==0:print('roots',i+1,'of',len(roots),flush=True)
    f.write(json.dumps(dict(type='complete'))+'\n');f.flush()
print('complete',a.phase,a.lane,flush=True)
