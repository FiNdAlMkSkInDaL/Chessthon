"""Mine actual qsearch stand-pat states; offline teacher labels; original replay fits."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,json,sys,time,shutil,inspect
from pathlib import Path
import numpy as np,chess,chess.engine
from train import HERE,ROOT,OLD,sha
from frontier import transfer
from turn_model import fit,turn_forward

TRACE='''
        if nn_acc[2,1]:
            nn_acc[2,0]+=1
            if nn_acc[2,0]%257==0:
                row=3+(nn_acc[2,0]//257)%64
                for piece in range(12):
                    nn_acc[row,2*piece]=np.int32(bb[piece]&np.uint64(0xffffffff))
                    nn_acc[row,2*piece+1]=np.int32(bb[piece]>>np.uint64(32))
                nn_acc[row,24]=np.int32(st[SIDE])
                nn_acc[row,25]=np.int32(st[CASTLE])
                nn_acc[row,26]=np.int32(st[EP])
                nn_acc[row,27]=np.int32(st[FIFTY])
                nn_acc[row,28]=np.int32(st[FULL])
                nn_acc[row,29]=stand
                nn_acc[row,30]=ply
                nn_acc[row,31]=beta
'''

def collect(a):
    dest=HERE/'frontier/search-states';dest.mkdir(parents=True,exist_ok=False);src=dest/'collector';src.mkdir()
    for p in (HERE/'frontier/native/turn').iterdir():
        if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
    s=(src/'core_nb.py').read_text();old='NN_ACC = np.tile(NET[768].astype(np.int32), (2,1))';assert old in s;s=s.replace(old,old+'\nNN_ACC = np.concatenate([NN_ACC,np.zeros((65,32),np.int32)])')
    needle='        stand = evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc)';assert s.count(needle)==1;s=s.replace(needle,needle+TRACE);(src/'core_nb.py').write_text(s)
    # train modules inserted Tempest path for evaluation tables, not core imports.
    sys.path.insert(0,str(src));start=time.perf_counter()
    import agent,core_nb as c,history
    from board_nb import from_fen,move_uci
    from movegen_nb import generate_legal
    assert c.NUMBA_READY
    original=inspect.getsource(c.search_root);fixed=original.replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative','max_nodes = _LAB_NODE_LIMIT');exec(compile(fixed,'<mining-fixed-nodes>','exec'),c.__dict__);c._LAB_NODE_LIMIT=200000
    snapshot={k:v.copy() for k,v in vars(c).items() if isinstance(v,np.ndarray) and v.flags.writeable}
    groups=json.loads((HERE/'frontier/decisions/groups.json').read_text());train=[r for r in groups if r['split']==0][:64];dev=[r for r in groups if r['split']==1][:16];roots=train+dev
    plan=dict(roots=[{k:r[k] for k in ('key','fen','split')} for r in roots],samples_per_root=32,nodes=200000,source={p.name:sha(p) for p in src.iterdir() if p.suffix in ('.py','.npz')},scope='Actual noncheck qsearch stand-pat states, systematic257-call ring sampling. Root families split BEFORE labels. No game-history reconstruction; teacher labels use recorded FEN rights/ep/halfmove. Search may have visited null branches. Public and prior development already exposed.')
    (dest/'plan.json').write_text(json.dumps(plan,indent=2));seen={};rows=[]
    def run(r,enabled):
        for k,v in snapshot.items():np.copyto(getattr(c,k),v)
        history.reset();b=chess.Board(r['fen']);history.observe_served(b);c.NN_ACC[2,1]=enabled;pos=from_fen(b.fen());m=c.search_root(pos,generate_legal(pos),1e12,1e12,False,history.zkeys().copy());return move_uci(m),c.last_info()
    with (dest/'roots.jsonl').open('x') as f:
        for i,r in enumerate(roots):
            if i<2:off=run(r,False)
            move,info=run(r,True)
            if i<2:assert (move,info['nodes'],info['score'])==(off[0],off[1]['nodes'],off[1]['score'])
            trace=c.NN_ACC[3:].copy();out=[]
            for row in trace:
                if row[30]<=0:continue
                b=chess.Board(None)
                for p in range(12):
                    bits=(int(row[2*p])&0xffffffff)|((int(row[2*p+1])&0xffffffff)<<32)
                    for sq in chess.scan_forward(bits):b.set_piece_at(sq,chess.Piece(p%6+1,p<6))
                b.turn=bool(row[24]==0);rights=int(row[25]);b.castling_rights=(chess.BB_H1 if rights&1 else 0)|(chess.BB_A1 if rights&2 else 0)|(chess.BB_H8 if rights&4 else 0)|(chess.BB_A8 if rights&8 else 0);b.ep_square=None if int(row[26])==64 else int(row[26]);b.halfmove_clock=int(row[27]);b.fullmove_number=max(1,int(row[28]))
                assert b.is_valid(),(b.fen(),b.status(),row.tolist())
                if b.is_game_over() or b.is_check():continue
                fen=b.fen();key=min(' '.join(fen.split()[:4]),' '.join(b.mirror().fen().split()[:4]))
                if key in seen:continue
                seen[key]=r['split'];out.append(dict(fen=fen,key=key,root=r['key'],split=r['split'],stand=int(row[29]),ply=int(row[30]),beta=int(row[31])))
            # Stable random subsampling, not score cherry-picking.
            rng=np.random.default_rng(int(r['key'][:8],16));rng.shuffle(out);rows.extend(out[:32]);f.write(json.dumps(dict(root=r['key'],uci=move,info=info,samples=min(32,len(out))))+'\n');f.flush()
    # Remove exact/mirrored overlap with all opposite-split root states and sampled leaves.
    rootkeys={}
    for r in roots:
        b=chess.Board(r['fen']);key=min(' '.join(b.fen().split()[:4]),' '.join(b.mirror().fen().split()[:4]));rootkeys.setdefault(key,set()).add(r['split'])
    rows=[r for r in rows if not any(s!=r['split'] for s in rootkeys.get(r['key'],set()))]
    (dest/'states.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(dest/'complete.json').write_text(json.dumps(dict(rows=len(rows),roots=len(roots),trace_on_off_identity=2,seconds=time.perf_counter()-start)))
    print('mined',len(rows),'states',flush=True)

def label(a):
    from policy import EXE
    dest=HERE/'frontier/search-states';rows=[json.loads(l) for l in (dest/'states.jsonl').read_text().splitlines()][a.lane::2];teacher_hash=sha(EXE)
    with (dest/f'labels-{a.lane}.jsonl').open('x') as f,chess.engine.SimpleEngine.popen_uci(str(EXE)) as engine:
        engine.configure({'Threads':1,'Hash':32})
        for i,r in enumerate(rows):
            b=chess.Board(r['fen']);engine.configure({'Clear Hash':None});chosen=None
            with engine.analysis(b,chess.engine.Limit(nodes=16000),game=object()) as analysis:
                for fresh in analysis:
                    if fresh.get('score') is not None and fresh.get('pv') and not fresh.get('lowerbound') and not fresh.get('upperbound'):chosen=dict(fresh)
            assert chosen is not None;score=chosen['score'].white();f.write(json.dumps(dict(**r,white_cp=score.score(),white_mate=score.mate(),nodes=chosen.get('nodes'),depth=chosen.get('depth'),teacher_nodes=16000,teacher_sha256=teacher_hash))+'\n');f.flush()
            if i%200==0:print(i,flush=True)
        f.write(json.dumps(dict(type='complete'))+'\n')

def adapt(a):
    from representations import encode
    from public_data_prepare import phase,pesto
    dest=HERE/f'frontier/leaf-{a.seed}';dest.mkdir(parents=True,exist_ok=False);rows=[]
    for p in sorted((HERE/'frontier/search-states').glob('labels-?.jsonl')):
        z=[json.loads(l) for l in p.read_text().splitlines()];assert z[-1]['type']=='complete';rows.extend(r for r in z[:-1] if r['white_mate'] is None and abs(r['white_cp'])<2500)
    x=np.zeros((len(rows),2,32),np.int32);counts=np.zeros((len(rows),2),np.int32);base=[];phs=[];turn=[]
    for i,r in enumerate(rows):
        b=chess.Board(r['fen']);ph=phase(b);base.append(pesto(b,ph));phs.append(ph);turn.append(1 if b.turn else -1)
        for v,z in enumerate(encode(b,'piece')):counts[i,v]=len(z);x[i,v,:len(z)]=z
    data=dict(x=x,counts=counts,base=np.array(base,np.float32),phase=np.array(phs,np.float32),turn=np.array(turn,np.int8),y=np.array([r['white_cp'] for r in rows],np.float32),quiet=np.ones(len(rows),bool),weights=np.ones(len(rows),np.float32))
    masks=[np.array([r['split']==s for r in rows]) for s in (0,1)];tt,td=[{k:v[mask] for k,v in data.items()} for mask in masks];oldtr,olddev=transfer()
    # Remove any opposite-split exact/mirror leakage into replay from the prior corpus.
    oldrows=[json.loads(l) for l in (OLD/'data/rows.jsonl').read_text().splitlines()];oldtrain=[r for r in oldrows if r['split']=='train'];devkeys={r['key'] for r in rows if r['split']==1};keep=[]
    for r in oldtrain:
        b=chess.Board(r['fen']);key=min(' '.join(b.fen().split()[:4]),' '.join(b.mirror().fen().split()[:4]));keep.append(key not in devkeys)
    keep=np.array(keep);oldtr={k:v[keep] for k,v in oldtr.items()}
    # Per-origin balancing prevents the much larger old corpus from drowning mined leaves.
    weight={260913:1.,260914:3.}[a.seed];tt['weights']*=weight*len(oldtr['y'])/len(tt['y'])
    merged={k:np.concatenate([tt[k],oldtr[k]]) for k in data};source=HERE/'turn-aware/s260909/adapted.npz';z=np.load(source);par=[z[k] for k in ('w','bias','out')]
    before={name:float(np.mean(abs(d['y']-(d['base']+400*turn_forward(d['x'],d['counts'],d['phase'],d['turn'],*par))))) for name,d in [('mined',td),('old',olddev)]}
    par,r,_=fit(merged,td,par,a.seed,20,.00015);np.savez_compressed(dest/'adapted.npz',w=par[0],bias=par[1],out=par[2]);after_old=float(np.mean(abs(olddev['y']-(olddev['base']+400*turn_forward(olddev['x'],olddev['counts'],olddev['phase'],olddev['turn'],*par)))))
    (dest/'result.json').write_text(json.dumps(dict(before=before,after_old_mae=after_old,result=r,weight=weight,train_rows=len(tt['y']),dev_rows=len(td['y']),source_sha256=sha(source),script_sha256=sha(__file__),scope='Actual qsearch stand-pat replay adaptation; finite teacher labels with no reconstructed repetition history. Reused root development, no strength claim.'),indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('collect','label','adapt'));ap.add_argument('--cpu',type=int,default=4);ap.add_argument('--lane',type=int,default=0);ap.add_argument('--seed',type=int,default=260913);a=ap.parse_args()
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(a.cpu)['applied']
    globals()[a.mode](a)
