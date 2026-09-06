"""Original isolated ablation driver; explicit baseline and instrumentation hashes."""
import os,sys,json,time,inspect,hashlib,argparse,copy,platform
from pathlib import Path
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
H=Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(R));sys.dont_write_bytecode=True
ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True);ap.add_argument('--cpu',type=int,default=4);ap.add_argument('--wide',action='store_true');ap.add_argument('--deep',action='store_true');ap.add_argument('--cases',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args()
from lab.laptop_runner import apply_windows_affinity
if os.name=='nt':assert apply_windows_affinity(a.cpu)['applied']
else:os.sched_setaffinity(0,{a.cpu})
import numpy as np,chess
source=H/'prototypes'/a.variant
def hashes(p):return {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.glob('*.py'))}
if not source.exists():
    source.mkdir(parents=True)
    for p in (R/'odin_v6').glob('*.py'):(source/p.name).write_bytes(p.read_bytes())
    p=source/'core_nb.py';s=p.read_text()
    changes={'baseline':{},'lmr_off':{'LMR_MIN_D = 3':'LMR_MIN_D = 99'},'futility_off':{'RFP_MAX_D = 6':'RFP_MAX_D = 0','FF_MAX_D = 2':'FF_MAX_D = 0'},'see_off':{'SEE_PRUNE_MAX_D = 6':'SEE_PRUNE_MAX_D = 0','see_bad = move != hash_move and see_nb(bb, mb, st, move) < 0':'see_bad = False'},'null_off':{'NMP_MIN_D = 3':'NMP_MIN_D = 99'},'pesto_only':{'return np.int32(pesto_nb(bb,st,True)+correction)':'return np.int32(pesto_nb(bb,st,True))'}}[a.variant]
    for old,new in changes.items():assert s.count(old)==1,(a.variant,old);s=s.replace(old,new)
    p.write_text(s,encoding='utf-8')
before=hashes(source);sys.path.insert(0,str(source));start=time.perf_counter()
import agent,core_nb as core,history
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert core.NUMBA_READY and core.root_search_nb.nopython_signatures
cold=time.perf_counter()-start;sig=list(map(str,core.root_search_nb.nopython_signatures))
snapshot={k:v.copy() for k,v in vars(core).items() if isinstance(v,np.ndarray)}
original=inspect.getsource(core.search_root)
fixed=original.replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative','max_nodes = _LAB_NODE_LIMIT')
assert fixed!=original
wall_driver=core.search_root;exec(compile(fixed,'<tempest-node-driver>','exec'),core.__dict__);node_driver=core.search_root
forced_source=fixed.replace('root_moves=nroot','root_moves=max(2,nroot)')
exec(compile(forced_source,'<tempest-forced-node-driver>','exec'),core.__dict__);forced_driver=core.search_root
def reset(c):
    for k,v in snapshot.items():np.copyto(getattr(core,k),v)
    history.reset();b=chess.Board(c['start_fen']);own=c['storm_colour']=='white'
    for u in c['history_uci']:
        if b.turn==own:history.observe_served(b);history.observe_our_uci(b,u)
        b.push_uci(u)
    assert b.fen()==c['fen'];history.observe_served(b);return b
def run(c,mode,budget,restrict=None):
    b=reset(c);p=from_fen(b.fen(en_passant='fen'));roots=generate_legal(p)
    if restrict:roots=[m for m in roots if move_uci(m)==restrict]
    pre=(p.bb.copy(),p.key)
    core._LAB_NODE_LIMIT=budget
    driver=(forced_driver if restrict else node_driver) if mode=='nodes' else wall_driver
    t=time.perf_counter();m=driver(p,roots,1e12 if mode=='nodes' else budget,1e12 if mode=='nodes' else budget,False,history.zkeys().copy());dt=time.perf_counter()-t
    assert list(map(str,core.root_search_nb.nopython_signatures))==sig
    assert np.array_equal(p.bb,pre[0]) and p.key==pre[1]
    u=move_uci(m);assert chess.Move.from_uci(u) in b.legal_moves
    return dict(id=c['id'],mode=mode,budget=budget,uci=u,san=b.san(chess.Move.from_uci(u)),seconds=dt,info=core.last_info(),restricted=restrict)
plan=json.loads((H/'experiment-plan.json').read_text());cases=json.loads((a.cases or H/'corpus-v1.json').read_text());focus=cases if a.cases else [c for c in cases if c['id'] in plan['focus']]
if a.deep:focus=[c for c in focus if c['source_kind']=='own-known']
path=a.output or H/(a.variant+'-probes.jsonl')
with path.open('x') as out:
    def emit(r):out.write(json.dumps(r)+'\n');out.flush()
    emit(dict(type='metadata',variant=a.variant,source_hashes=before,baseline_hashes=hashes(R/'odin_v6'),cold_seconds=cold,python=platform.python_version(),machine=platform.machine(),cpu=a.cpu,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),plan_sha256=hashlib.sha256((H/'experiment-plan.json').read_bytes()).hexdigest(),driver_sha256=hashlib.sha256(fixed.encode()).hexdigest(),native_ready=True))
    x=run(focus[0],'nodes',20000);run(focus[-1],'nodes',20000);y=run(focus[0],'nodes',20000)
    assert [x['uci'],x['info']['nodes'],x['info']['score'],x['info']['depth']]==[y['uci'],y['info']['nodes'],y['info']['score'],y['info']['depth']]
    emit(dict(type='isolation',pass_ABA=True,a=x,b=y))
    for c in (cases if a.wide else focus):
        if c['split']!='discovery':continue
        if a.deep:
            refs=[json.loads(s) for s in (H/'reference-corpus.jsonl').read_text().splitlines()]
            ref=next(r for r in refs if r.get('id')==c['id'])
            emit(dict(type='probe',**run(c,'nodes',4000000)))
            candidates={c['played_uci'],ref['best']['pv_uci'][0]}
            oldrefs=[json.loads(s) for s in (R/'lab/odin/day3/deep-reference.jsonl').read_text().splitlines()]
            oldref=next(r for r in oldrefs if r['id']==c['id']);candidates.add(oldref['best']['pv_uci'][0])
            for u in sorted(candidates):emit(dict(type='probe',**run(c,'nodes',1000000,u)))
            # Static evaluation on reference PV is a horizon diagnostic, not a searched score.
            b=reset(c);curve=[]
            for u in ref['best']['pv_uci'][:16]:
                b.push_uci(u);bb,mb,st=core.pack_pos(from_fen(b.fen(en_passant='fen')));curve.append(dict(uci=u,fen=b.fen(),white_static=int(core.evaluate_nb(bb,st,False))*(1 if b.turn else -1)))
            emit(dict(type='pv_static',id=c['id'],curve=curve));print('deep',c['id'],flush=True);continue
        budgets=[('nodes',n) for n in plan['budgets']]+[('wall',plan['wall_ms'])] if c in focus else [('nodes',200000)]
        # Static candidate ranking is deliberately separated from searched values.
        b=reset(c);ranking=[]
        for m in b.legal_moves:
            b.push(m);bb,mb,st=core.pack_pos(from_fen(b.fen(en_passant='fen')))
            ranking.append([m.uci(),-int(core.evaluate_nb(bb,st,False))]);b.pop()
        emit(dict(type='static',id=c['id'],ranking=sorted(ranking,key=lambda x:-x[1])))
        for mode,n in budgets:
            r=run(c,mode,n);emit(dict(type='probe',**r));print(a.variant,c['id'],mode,n,r['san'],r['info']['depth'],flush=True)
    assert hashes(source)==before
    emit(dict(type='complete',source_unchanged=True,signatures_unchanged=True))
