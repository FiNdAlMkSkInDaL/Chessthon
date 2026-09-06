"""Complete-alternative teacher labels and original value-conditioned policy."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import argparse,concurrent.futures as cf,hashlib,json,sys,time
from pathlib import Path
import chess,chess.engine,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'lab/agamemnon'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OLD))
from representations import encode,forward,sha
from public_data_prepare import phase,pesto
EXE=Path('C:/Users/finla/AppData/Local/ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe')
DATASET='policy'
NAMES=['piece_p','piece_n','piece_b','piece_r','piece_q','piece_k','capture_p','capture_n','capture_b','capture_r','capture_q','capture_k','promote_n','promote_b','promote_r','promote_q','check','castle','pesto_delta','neural_delta','enemy_pawn_to','own_pawn_to','pawn_advance','enemy_king_approach','own_king_approach','phase','center_gain','from_rank','to_rank','from_file','to_file','capture']
def features(b,m,before,after):
    c=b.turn;p=b.piece_type_at(m.from_square);a=m.from_square;t=m.to_square;f=np.zeros(32,np.float32);f[p-1]=1
    cap=1 if b.is_en_passant(m) else b.piece_type_at(t)
    if cap:f[5+cap]=1
    if m.promotion:f[10+m.promotion]=1
    f[16]=b.gives_check(m);f[17]=b.is_castling(m);ph=phase(b);base=pesto(b,ph);sign=1 if c else -1
    f[19]=sign*(after-before)/400;f[20]=bool(chess.BB_PAWN_ATTACKS[c][t]&b.pieces_mask(1,not c));f[21]=bool(chess.BB_PAWN_ATTACKS[not c][t]&b.pieces_mask(1,c))
    f[22]=(t//8-a//8)*sign if p==1 else 0
    ok=b.king(not c);own=b.king(c)
    f[23]=chess.square_distance(a,ok)-chess.square_distance(t,ok);f[24]=0 if p==6 else chess.square_distance(a,own)-chess.square_distance(t,own)
    f[25]=ph;dist=lambda s:abs(2*(s%8)-7)+abs(2*(s//8)-7)
    f[26]=(dist(a)-dist(t))/4;f[27]=(a//8 if c else 7-a//8)/7;f[28]=(t//8 if c else 7-t//8)/7;f[29]=(a%8)/7;f[30]=(t%8)/7;f[31]=b.is_capture(m)
    b.push(m);f[18]=sign*(pesto(b,phase(b))-base)/100;b.pop();return f
def label_lane(lane):
    lane,dataset=lane
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(6+lane)['applied'];dest=HERE/dataset;plan=json.loads((dest/'plan.json').read_text());rows=plan['roots'][lane::2]
    with (dest/f'labels-{lane}.jsonl').open('x') as out,chess.engine.SimpleEngine.popen_uci(str(EXE)) as engine:
        engine.configure({'Threads':1,'Hash':32})
        for i,r in enumerate(rows):
            b=chess.Board(r['fen']);legal=list(b.legal_moves);engine.configure({'Clear Hash':None})
            if plan.get('forced'):
                infos=[]
                for move in legal:
                    engine.configure({'Clear Hash':None})
                    if plan.get('exact_iterations'):
                        chosen=None
                        with engine.analysis(b,chess.engine.Limit(nodes=16000),root_moves=[move],game=object()) as analysis:
                            for fresh in analysis:
                                if fresh.get('score') is not None and fresh.get('pv') and not fresh.get('lowerbound') and not fresh.get('upperbound'):
                                    assert fresh['pv'][0]==move;chosen=dict(fresh)
                        assert chosen is not None,(r['fen'],move)
                        infos.append(chosen)
                    else:infos.append(engine.analyse(b,chess.engine.Limit(nodes=16000),root_moves=[move],game=object()))
            else:infos=engine.analyse(b,chess.engine.Limit(nodes=64000),multipv=len(legal),game=object())
            moves=[]
            for info in infos:
                m=info['pv'][0];score=info['score'].pov(b.turn)
                moves.append(dict(uci=m.uci(),cp=score.score(mate_score=10000),mate=score.mate(),depth=info.get('depth'),nodes=info.get('nodes'),lowerbound=bool(info.get('lowerbound')),upperbound=bool(info.get('upperbound'))))
            assert {m['uci'] for m in moves}=={m.uci() for m in legal} and len(moves)==len(legal)
            out.write(json.dumps(dict(**r,moves=moves))+'\n');out.flush()
            if i%32==0:print('policy-labels',lane,i+1,flush=True)
        out.write(json.dumps(dict(type='complete'))+'\n')
    return len(rows)
def label():
    dest=HERE/DATASET;dest.mkdir(exist_ok=False);roots=[];seen=set()
    for i in range(64):
        for r in json.loads((HERE/f'data/roots-{i:03d}.json').read_text()):
            if r['key'] in seen:continue
            seen.add(r['key']);r['split']=int(i>=48);roots.append(r)
    assert len(roots)==512
    plan=dict(roots=roots,teacher_sha256=sha(EXE),nodes=16000 if DATASET!='policy' else 64000,forced=DATASET!='policy',exact_iterations=DATASET=='policy-exact',threads=1,scope='512 public training-object roots. Whole-root train/development partition fixed before label acquisition. Finite teacher evidence, not exact minimax. Forced mode spends16k nodes independently per move with cleared hash; original mode shares64k across MultiPV. Exact_iterations retains latest fresh unbounded score-bearing PV; does not inherit stale bound flags from aggregated analysis dictionaries. All alternatives required.',script_sha256=sha(__file__))
    (dest/'plan.json').write_text(json.dumps(plan,indent=2))
    with cf.ProcessPoolExecutor(max_workers=2) as pool:print(list(pool.map(label_lane,((0,DATASET),(1,DATASET)))),flush=True)
def predictions(boards,par):
    n=len(boards);x=np.zeros((n,2,32),np.int32);counts=np.zeros((n,2),np.int32);ph=np.zeros(n,np.float32);base=ph.copy()
    for i,b in enumerate(boards):
        for side,ids in enumerate(encode(b,'piece')):x[i,side,:len(ids)]=ids;counts[i,side]=len(ids)
        ph[i]=phase(b);base[i]=pesto(b,ph[i])
    if par[2].shape[1]==4:
        from turn_model import turn_forward
        turns=np.array([1 if b.turn else -1 for b in boards],np.int8)
        return base+400*turn_forward(x,counts,ph,turns,*par)
    return base+400*forward(x,counts,ph,*par,1)
def fit(checkpoint,name):
    checkpoint=checkpoint.resolve()
    dest=HERE/DATASET;outdir=dest/name;outdir.mkdir(exist_ok=False);z=np.load(checkpoint);par=[z[k] for k in ('w','bias','out')];rows=[]
    for lane in (0,1):
        ll=[json.loads(l) for l in (dest/f'labels-{lane}.jsonl').open()];assert ll[-1]['type']=='complete';rows+=ll[:-1]
    # Exclude bounded teacher estimates from fitting rather than treating a bound as exact.
    rows=[r for r in rows if not any(m['lowerbound'] or m['upperbound'] for m in r['moves'])]
    raw=[];scores=[];starts=[];ends=[];split=[]
    for r in rows:
        b=chess.Board(r['fen']);boards=[b.copy()]
        for m in r['moves']:bb=b.copy();bb.push_uci(m['uci']);boards.append(bb)
        pred=predictions(boards,par);starts.append(len(raw))
        for i,m in enumerate(r['moves']):raw.append(features(b,chess.Move.from_uci(m['uci']),pred[0],pred[i+1]));scores.append(m['cp'])
        ends.append(len(raw));split.append(r['split'])
    raw=np.array(raw);scores=np.array(scores);starts=np.array(starts);ends=np.array(ends);split=np.array(split);lengths=ends-starts
    x=np.concatenate([raw,*[raw[:,16:]*raw[:,j:j+1] for j in range(6)]],axis=1).astype(np.float64)
    # Soft preferences give near-equivalent alternatives credit. Label temperature fixed.
    target=np.empty(len(x))
    for st,en in zip(starts,ends):v=np.exp(np.maximum(-40,(scores[st:en]-scores[st:en].max())/100));target[st:en]=v/v.sum()
    tr=split==0;va=~tr;train_moves=np.repeat(tr,lengths);scale=np.sqrt(np.mean(x[train_moves]**2,axis=0));scale[scale<1e-5]=1;xx=x/scale
    coef=np.zeros(x.shape[1]);mom=coef.copy();var=coef.copy();curve=[]
    group_weights=np.repeat(tr/np.sum(tr),lengths)
    for step in range(1,401):
        logits=xx@coef;ex=np.exp(logits-np.repeat(np.maximum.reduceat(logits,starts),lengths));p=ex/np.repeat(np.add.reduceat(ex,starts),lengths)
        grad=xx.T@((p-target)*group_weights)+.001*coef;mom=.9*mom+.1*grad;var=.999*var+.001*grad*grad
        coef-=.025*(mom/(1-.9**step))/(np.sqrt(var/(1-.999**step))+1e-8)
    coef/=scale;logits=x@coef;trials=[]
    for temp in (.5,1.,2.,4.):
        for mix in (.1,.25,.5):
            rec=[]
            for st,en in zip(starts,ends):
                vv=logits[st:en]/temp;pp=np.exp(vv-vv.max());pp=(1-mix)*pp/pp.sum()+mix/(en-st);ss=scores[st:en]
                rec.append((-np.sum(target[st:en]*np.log(pp)),ss.max()-ss[np.argmax(pp)],pp[np.argmax(ss)]<1/(en-st)))
            rr=np.array(rec);trials.append(dict(temperature=temp,mix=mix,development_crossentropy=float(rr[va,0].mean()),development_regret_cp=float(rr[va,1].mean()),teacher_below_uniform=float(rr[va,2].mean())))
    choice=min(trials,key=lambda r:r['development_crossentropy']);uniform=float(np.mean(np.log(lengths[va])))
    controls={}
    for name_,col in [('pesto',18),('neural',19)]:controls[name_]=float(np.mean([scores[st:en].max()-scores[st+np.argmax(raw[st:en,col])] for st,en,s in zip(starts,ends,split) if s]))
    result=dict(checkpoint=str(checkpoint.relative_to(ROOT)),checkpoint_sha256=sha(checkpoint),script_sha256=sha(__file__),features=NAMES,groups=len(rows),moves=len(raw),train_groups=int(tr.sum()),development_groups=int(va.sum()),uniform_crossentropy=uniform,choice=choice,trials=trials,control_regret_cp=controls,coefficients=coef.tolist(),scope='Original soft full-alternative policy, reused public-source development calibration. Finite shallow MultiPV labels. Neural feature uses specified original evaluation checkpoint. No playing-strength claim.')
    (outdir/'result.json').write_text(json.dumps(result,indent=2));np.savez_compressed(outdir/'policy.npz',coef=coef.astype(np.float32),calibration=np.array([choice['temperature'],choice['mix']],np.float32))
    np.savez_compressed(outdir/'matrix.npz',raw=raw,scores=scores,starts=starts,ends=ends,split=split,logits=logits)
    (outdir/'cases.json').write_text(json.dumps([dict(fen=r['fen'],moves=r['moves']) for r in rows[:32]]));print(json.dumps({k:result[k] for k in ('groups','moves','uniform_crossentropy','choice','control_regret_cp')}),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--label',action='store_true');ap.add_argument('--checkpoint',type=Path);ap.add_argument('--name',default='original');ap.add_argument('--forced',action='store_true');ap.add_argument('--exact',action='store_true');a=ap.parse_args()
    if a.forced:DATASET='policy-forced'
    if a.exact:DATASET='policy-exact'
    if a.label:label()
    else:fit(a.checkpoint,a.name)
