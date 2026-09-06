"""Native candidate gates and source-bound full-history search diagnostics."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,inspect,json,sys,time,textwrap
from pathlib import Path
import chess,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True);ap.add_argument('--cpu',type=int,required=True);ap.add_argument('--cases',type=Path,required=True);ap.add_argument('--tag',required=True);ap.add_argument('--wall',action='store_true');a=ap.parse_args()
if os.name=='nt':
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(a.cpu)['applied']
else:os.sched_setaffinity(0,{a.cpu})
source=HERE/'prototypes'/a.variant;sys.path.insert(0,str(source))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes=lambda:{p.name:sha(p) for p in source.iterdir() if p.is_file() and p.suffix in ('.py','.npz')}
bound=hashes();t=time.perf_counter()
import agent,core_nb as core,history
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert core.NUMBA_READY and core.root_search_nb.nopython_signatures
cold=time.perf_counter()-t
snapshot={k:v.copy() for k,v in vars(core).items() if isinstance(v,np.ndarray) and v.flags.writeable}
original=inspect.getsource(core.search_root);wall_driver=core.search_root
fixed=original.replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative','max_nodes = _LAB_NODE_LIMIT')
assert fixed!=original;exec(compile(fixed,'<edges-fixed-nodes>','exec'),core.__dict__)
driver=core.search_root;cases=json.loads(a.cases.read_text())
def reset(c):
    for k,v in snapshot.items():np.copyto(getattr(core,k),v)
    history.reset();b=chess.Board(c['start_fen']);own=c['storm_colour']=='white'
    for u in c['history_uci']:
        if b.turn==own:history.observe_served(b);history.observe_our_uci(b,u)
        b.push_uci(u)
    assert b.fen()==c['fen'];history.observe_served(b);return b
def run(c,budget,wall=False):
    b=reset(c);pos=from_fen(b.fen(en_passant='fen'));legal=generate_legal(pos);core._LAB_NODE_LIMIT=budget
    t=time.perf_counter();m=(wall_driver if wall else driver)(pos,legal,budget if wall else 1e12,budget if wall else 1e12,False,history.zkeys().copy());seconds=time.perf_counter()-t
    u=move_uci(m);assert chess.Move.from_uci(u) in b.legal_moves
    r=dict(id=c['id'],budget=budget,mode='wall' if wall else 'nodes',uci=u,info=core.last_info().copy(),seconds=seconds)
    if len(core.TT_AGE)>1:r['tt_stats']=core.TT_AGE[1:].tolist()
    if core.HISTORY.shape[0]>12:
        h=core.HISTORY[12:];r['capture_history']=dict(nonzero=int(np.count_nonzero(h)),minimum=int(h.min()),maximum=int(h.max()))
        before=core.HISTORY.copy();core.HISTORY[12:]=0
        bb,mb,st=core.pack_pos(pos);plain=np.array(legal,np.int32);learned=plain.copy()
        core.sort_moves(mb,plain,len(plain),0,0,np.zeros_like(core.KILLERS),core.HISTORY)
        np.copyto(core.HISTORY,before);core.sort_moves(mb,learned,len(learned),0,0,np.zeros_like(core.KILLERS),core.HISTORY)
        r['capture_history']['root_order_changed']=not np.array_equal(plain,learned)
        assert h.min()>=-core.HISTORY_MAX and h.max()<=core.HISTORY_MAX
    return r
out=HERE/f'{a.variant}-{a.tag}.jsonl'
with out.open('x') as f:
    def emit(r):f.write(json.dumps(r)+'\n');f.flush()
    emit(dict(type='metadata',variant=a.variant,source_hashes=bound,cold_seconds=cold,script_sha256=sha(Path(__file__)),cases_sha256=sha(a.cases),scope='Development candidate gates and diagnostics, not a strength claim'))
    from lab.perft import POSITIONS
    for name,fen,expected in POSITIONS:assert core.perft_pos(from_fen(fen),3)==expected[3]
    # Exercise the actual source predicate against colour/queen/geometry boundaries.
    s=(source/'core_nb.py').read_text();start=s.index('            if reduction and mover % 6 == 0:') if '            if reduction and mover % 6 == 0:' in s else s.index('            if reduction and mover % 6 == 0 and bb[')
    end=s.index('        if searched == 0:',start)
    body=textwrap.dedent(s[start:end]);ns=dict(np=np,lsb=core.lsb)
    exec('def adjustment(reduction,mover,move,bb):\n'+textwrap.indent(body,'    ')+'    return reduction\n',dict(ns,m_to=core.m_to),ns)
    adjustment=ns['adjustment'];predicate_checks=0
    for color in range(2):
        for queen in (False,True):
            for ef in range(8):
                for er in (0,3,7):
                    bb=np.zeros(12,np.uint64);bb[(1-color)*6+5]=np.uint64(1)<<np.uint64(er*8+ef)
                    if queen:bb[color*6+4]=np.uint64(1)
                    for target in range(64):
                        near=abs((target&7)-ef)<=1 and abs((target>>3)-er)<=3
                        for reduction in (0,1,3):
                            expected=reduction
                            if near and ('queen' not in a.variant or queen):expected=max(0,reduction-1) if 'graded' in a.variant else 0
                            got=adjustment(reduction,color*6,np.int32(target<<6),bb)
                            assert got==expected,(color,queen,ef,er,target,reduction,got,expected)
                            predicate_checks+=1
    ordering_checks=0
    if core.HISTORY.shape[0]>12:
        b=chess.Board('4k3/8/8/2n2n2/3PP3/8/8/4K3 w - - 0 1');pos=from_fen(b.fen());bb,mb,st=core.pack_pos(pos)
        legal=generate_legal(pos);captures=[m for m in legal if core.m_cap(m)];assert len(captures)==2
        for preferred in captures:
            core.HISTORY.fill(0)
            for m in captures:
                p=int(mb[core.m_from(m)]);row=12+p*6+int(core.victim_pt(mb,m));core.HISTORY[row,core.m_to(m)]=core.HISTORY_MAX if m==preferred else -core.HISTORY_MAX
            moves=np.array(legal,np.int32);core.sort_moves(mb,moves,len(moves),0,0,np.zeros_like(core.KILLERS),core.HISTORY);assert moves[0]==preferred
            core.sort_moves(mb,moves,len(moves),0,captures[0],np.zeros_like(core.KILLERS),core.HISTORY);assert moves[0]==captures[0];ordering_checks+=1
        for bonus in (1600,-1600,100000,-100000):
            for _ in range(100):core.history_update(core.HISTORY,13,34,bonus)
            assert abs(core.HISTORY[13,34])<=core.HISTORY_MAX
    x=run(cases[0],20000);run(cases[-1],20000);y=run(cases[0],20000)
    ident=lambda r:(r['uci'],r['info']['score'],r['info']['depth'],r['info']['nodes'])
    assert ident(x)==ident(y)
    emit(dict(type='checks',perft_positions=len(POSITIONS),predicate_checks=predicate_checks,capture_order_checks=ordering_checks,ABA=True))
    for c in cases:
        for budget in c.get('wall_budgets',[500,2000]) if a.wall else c.get('budgets',[200000]):
            r=run(c,budget,a.wall);emit(dict(type='probe',**r));print(a.variant,c['id'],budget,r['uci'],r['info']['score'],flush=True)
    assert hashes()==bound;emit(dict(type='complete',source_unchanged=True))
