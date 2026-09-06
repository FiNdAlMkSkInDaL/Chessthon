"""Linux cold/perft/incremental parity and equal-node/equal-wall decision screen."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,inspect,json,sys,time
from pathlib import Path
import numpy as np,chess
ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True);ap.add_argument('--cpu',type=int,required=True);a=ap.parse_args();os.sched_setaffinity(0,{a.cpu})
HERE=Path(__file__).resolve().parent;src=HERE/a.variant;sys.path.insert(0,str(src));started=time.perf_counter()
import agent,core_nb as c,history
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert c.NUMBA_READY and c.root_search_nb.nopython_signatures;cold=time.perf_counter()-started;assert cold<80,cold
meta=json.loads((HERE/f'{a.variant}.json').read_text())
for name,h in meta['files'].items():assert hashlib.sha256((src/name).read_bytes()).hexdigest()==h
snapshot={k:v.copy() for k,v in vars(c).items() if isinstance(v,np.ndarray) and v.flags.writeable}
original=inspect.getsource(c.search_root);fixed=original.replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative','max_nodes = _LAB_NODE_LIMIT');assert fixed!=original;wall=c.search_root;exec(compile(fixed,'<frontier-fixed-nodes>','exec'),c.__dict__)
def reset():
    for k,v in snapshot.items():np.copyto(getattr(c,k),v)
    history.reset()
def static(b):
    bb,mb,st=c.pack_pos(from_fen(b.fen()))
    args=(c.NET,c.NN_LAST_BB,c.NN_ACC) if hasattr(c,'NET') else ()
    return int(c.evaluate_nb(bb,st,False,*args))
with (HERE/f'{a.variant}-results.jsonl').open('x') as out:
    def emit(r):out.write(json.dumps(r)+'\n');out.flush()
    emit(dict(type='metadata',cold_seconds=cold,cpu=a.cpu,**meta))
    for name,fen,expected in json.loads((HERE/'perft.json').read_text()):assert c.perft_pos(from_fen(fen),3)==expected['3'],name
    checks=0;maximum=0.
    if hasattr(c,'NET'):
        n=meta['features'];net=c.NET;mix=meta['mix']
        # Includes arbitrary jumps, king moves, captures, promotions and mirrored turns.
        for fen in json.loads((HERE/'parity.json').read_text()):
            b=chess.Board(fen);value=static(b);expected=np.tile(net[n].astype(np.int32),(2,1))
            for v,col in enumerate((chess.WHITE,chess.BLACK)):
                flip=0 if col else 56;king=b.king(col)^flip
                for sq,p in b.piece_map().items():
                    s=sq^flip;pt=p.piece_type-1+(0 if p.color==col else 6);expected[v]+=net[pt*64+s].astype(np.int32)
                    if n>768:expected[v]+=net[768+pt*225+(s//8-king//8+7)*15+s%8-king%8+7].astype(np.int32)
            assert np.array_equal(expected,c.NN_ACC),fen
            bb,mb,st=c.pack_pos(from_fen(fen));phase=min(24,int(st[c.PHASE_ACC]))/24;corr=0.
            for v in range(2):
                head=n+1 if v==int(st[c.SIDE]) else n+3
                corr+=np.dot(np.clip(expected[v]/4096.,0,2),phase*net[head]+(1-phase)*net[head+1])
            if net.shape[0]>773:
                mover=int(st[c.SIDE]);act=np.r_[np.clip(expected[mover]/4096.,0,2),np.clip(expected[1-mover]/4096.,0,2)]
                hidden=np.clip(act@net[773:837,:16]+net[837,:16],0,2)
                corr+=np.dot(hidden,phase*net[838,:16]+(1-phase)*net[839,:16])
            hand=c.positional_correction_nb(bb,st)*(1 if b.turn else -1);ref=c.pesto_nb(bb,st,True)+mix*400*corr+(1-mix)*hand
            maximum=max(maximum,abs(value-ref));assert abs(value-ref)<1.01,(fen,value,ref);checks+=1
    emit(dict(type='checks',perft=6,integer_accumulator_positions=checks,max_float_output_rounding_cp=maximum))
    roots=json.loads((HERE/'roots.json').read_text())
    def run(r,kind):
        reset();b=chess.Board(r['fen']);history.observe_served(b);pos=from_fen(b.fen());c._LAB_NODE_LIMIT=200000;t=time.perf_counter();ms=300 if kind=='wall' else 1e12
        m=(wall if kind=='wall' else c.search_root)(pos,generate_legal(pos),ms,ms,False,history.zkeys().copy());uci=move_uci(m);assert chess.Move.from_uci(uci) in b.legal_moves
        scores={m['uci']:m['cp'] for m in r['moves']};regret=max(scores.values())-scores[uci]
        return dict(type='decision',key=r['key'],kind=kind,uci=uci,regret=regret,seconds=time.perf_counter()-t,info=c.last_info())
    first=run(roots[0],'nodes');run(roots[-1],'nodes');again=run(roots[0],'nodes');assert(first['uci'],first['info']['score'],first['info']['nodes'])==(again['uci'],again['info']['score'],again['info']['nodes']);emit(dict(type='isolation',ABA=True))
    for r in roots:
        for kind in ('nodes','wall'):emit(run(r,kind))
    emit(dict(type='complete'))
print(a.variant,'complete',flush=True)
