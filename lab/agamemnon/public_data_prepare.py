"""Verify public label orientation, deduplicate, and build original-model inputs.
No private holdout or sealed public blocks are opened. SF is offline audit only.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import hashlib,json,math,sys,time
from pathlib import Path
import chess,chess.engine,numpy as np
from representations import encode,load_data,sha,HERE,ROOT
sys.path.insert(0,str(ROOT/'tempest_exact'))
from eval_nb import MG_TABLE,EG_TABLE

def key(b):return ' '.join(b.fen(en_passant='legal').split()[:4])
def phase(b):return min(24,sum(len(b.pieces(pt,c))*v for pt,v in [(2,1),(3,1),(4,2),(5,4)] for c in (True,False)))/24
def pesto(b,ph):
    mg=eg=0
    for sq,p in b.piece_map().items():
        idx=p.piece_type-1+(0 if p.color else 6);sign=1 if p.color else -1
        mg+=sign*MG_TABLE[idx][sq];eg+=sign*EG_TABLE[idx][sq]
    return mg*ph+eg*(1-ph)+(10 if b.turn else -10)

def pack(rows,dest,name):
    n=len(rows);data={k:np.zeros(n,np.float32) for k in ('phase','base','y','weights')};data['split']=np.zeros(n,np.int8);data['quiet']=np.zeros(n,bool)
    encoded={rep:np.zeros((n,2,64 if rep=='relative' else 32),np.int32) for rep in ('piece','relative')};ns={rep:np.zeros((n,2),np.int32) for rep in encoded}
    for i,r in enumerate(rows):
        b=chess.Board(r['fen']);ph=phase(b);q=not b.is_check() and not any(b.is_capture(m) or m.promotion for m in b.legal_moves)
        data['phase'][i]=ph;data['base'][i]=pesto(b,ph);data['y'][i]=r['white_cp'];data['quiet'][i]=q;data['weights'][i]=1 if q else .25;data['split'][i]=r['split']
        for rep in encoded:
            for side,z in enumerate(encode(b,rep)):encoded[rep][i,side,:len(z)]=z;ns[rep][i,side]=len(z)
    for rep in encoded:np.savez_compressed(dest/f'{name}-{rep}.npz',x=encoded[rep],counts=ns[rep],**data)
    return dict(rows=n,train=int(sum(data['split']==0)),development=int(sum(data['split']==1)),quiet=int(data['quiet'].sum()),base_mae=float(np.mean(abs(data['base']-data['y']))))

def main():
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(2)['applied'];dest=HERE/'public-data';dest.mkdir(exist_ok=False);started=time.perf_counter()
    source=HERE/'chessbench';rows=[]
    for p in sorted(source.glob('rows-*.jsonl')):
        for line in p.open():
            r=json.loads(line);prob=r['win_probability']
            if not .001<prob<.999:continue
            b=chess.Board(r['fen'])
            if b.halfmove_clock>=80 or b.ply()>=500 or b.is_game_over() or b.is_repetition(3):continue
            r['logit_cp']=math.log(prob/(1-prob))/.00368208
            rows.append(r)
    # Side-to-move versus White orientation is verified against independent finite SF19.
    sample=sorted((r for r in rows if 120<abs(r['logit_cp'])<800),key=lambda r:hashlib.sha256(r['fen'].encode()).hexdigest())[:48]
    exe=Path('C:/Users/finla/AppData/Local/ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe')
    audit=[]
    with chess.engine.SimpleEngine.popen_uci(str(exe)) as engine:
        engine.configure({'Threads':1,'Hash':16})
        for r in sample:
            b=chess.Board(r['fen']);engine.configure({'Clear Hash':None});info=engine.analyse(b,chess.engine.Limit(nodes=64000),game=object());score=info['score'].white().score(mate_score=2000)
            audit.append(dict(fen=r['fen'],public_cp=r['logit_cp'],reference_white_cp=score,turn=b.turn))
    whiteerr=np.mean([abs(r['public_cp']-r['reference_white_cp']) for r in audit]);stmerr=np.mean([abs(r['public_cp']*(1 if r['turn'] else -1)-r['reference_white_cp']) for r in audit])
    assert min(whiteerr,stmerr)<max(whiteerr,stmerr)*.5,(whiteerr,stmerr)
    orientation='side_to_move' if stmerr<whiteerr else 'white'
    audit_report=dict(orientation=orientation,white_hypothesis_mae=whiteerr,stm_hypothesis_mae=stmerr,reference_sha256=sha(exe),reference_nodes=64000,sample=audit,scope='Empirical orientation audit, finite different-version teacher; not label equivalence or strength.')
    (dest/'orientation-audit.json').write_text(json.dumps(audit_report,indent=2));print(orientation,whiteerr,stmerr,flush=True)
    strong,labels,_=load_data();oldkeys={key(chess.Board(r['fen'])) for r in strong}
    # Validation blocks win exact/mirror collisions. Other transposition/game overlaps
    # cannot be ruled out without original game IDs; disclose this limitation.
    positions={};removed_old=dupes=0
    def canonical(b):return min(key(b),key(b.mirror()))
    oldkeys={canonical(chess.Board(r['fen'])) for r in strong}
    for r in sorted(rows,key=lambda r:(r['block']<16,r['record_index'])):
        b=chess.Board(r['fen']);k=canonical(b)
        if k in oldkeys:removed_old+=1;continue
        if k in positions:dupes+=1;continue
        positions[k]=dict(fen=r['fen'],white_cp=r['logit_cp']*(1 if orientation=='white' or b.turn else -1),split=0 if r['block']<16 else 1,block=r['block'],record_index=r['record_index'])
    rows=sorted(positions.values(),key=lambda r:hashlib.sha256(('agamemnon-public-shuffle1'+r['fen']).encode()).hexdigest())
    (dest/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    stats=pack(rows,dest,'public')
    transfer=[dict(fen=r['fen'],white_cp=labels[r['id']]['white_cp'],split=0 if r['split']=='train' else 1) for r in strong]
    transferstats=pack(transfer,dest,'transfer')
    (dest/'manifest.json').write_text(json.dumps(dict(stats=stats,transfer=transferstats,orientation=orientation,old_exact_or_mirror_removed=removed_old,duplicates_removed=dupes,seconds=time.perf_counter()-started,sources={'public_manifest':sha(source/'manifest.json'),'script':sha(__file__),'encoder':sha(HERE/'representations.py')},scope='Public blocks split before labels; no exact/mirror collisions across public partitions or old Tempest states. Missing game IDs prevent opening-family independence claims. Teacher cp inversion uses published logistic mapping; SF16 labels and SF19 transfer labels have different calibration. Sealed blocks untouched.'),indent=2));print(stats,flush=True)
if __name__=='__main__':main()
