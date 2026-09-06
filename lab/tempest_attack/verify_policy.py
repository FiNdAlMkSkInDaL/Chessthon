"""Native/reference parity, move-order priorities and complete board restoration."""
import os,sys,time,json,hashlib
from pathlib import Path
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(8)['applied']
source=HERE/'prototypes/policy_cheap';sys.path.insert(0,str(source));began=time.perf_counter()
import agent,core_nb as core,numpy as np,chess
from board_nb import from_fen,move_uci
from movegen_nb import generate_legal
assert core.NUMBA_READY;cold=time.perf_counter()-began
from policy_prior import features,NAMES
model=json.loads((HERE/'policy-cheap/result.json').read_text());keep=[NAMES.index(n) for n in model['plan']['kept_features']];weights=np.array(model['collapsed_coefficients'])
states={r['id']:r for r in map(json.loads,(ROOT/'lab/tempest_build/data/states.jsonl').read_text().splitlines())}
groups=json.loads((HERE/'policy/groups.json').read_text());count=0;maxerr=0.;tested=[]
for row in groups[::13]:
    b=chess.Board(states[row['id']]['fen']);pos=from_fen(b.fen(en_passant='fen'));bb,mb,st=core.pack_pos(pos)
    before=[v.copy() for v in (bb,mb,st)]
    legal=generate_legal(pos);quiet=[m for m in legal if not (core.m_cap(m) or core.m_promo(m))]
    for m in quiet:
        move=chess.Move.from_uci(move_uci(m));f=features(b,move)[keep];pt=b.piece_type_at(move.from_square)-1
        expected=np.concatenate([[1],f[6:]])@weights[pt]
        got=core.quiet_prior_value_nb(bb,mb,st,np.int32(m));maxerr=max(maxerr,abs(got-expected));assert abs(got-expected)<1e-6,(b.fen(),move,got,expected)
        count+=1
    assert all(np.array_equal(a,z) for a,z in zip(before,(bb,mb,st)))
    if len(quiet)>=3:
        # Nonzero history always dominates a learned zero-history score.
        for m,v in zip(quiet[:3],[1,0,-1]):core.HISTORY[mb[core.m_from(m)],core.m_to(m)]=v
        moves=np.array(quiet[:3][::-1],np.int32);killers=np.zeros_like(core.KILLERS)
        core.sort_moves(bb,st,mb,moves,len(moves),0,0,killers,core.HISTORY)
        assert list(moves)==list(quiet[:3]);core.HISTORY.fill(0)
        moves=np.array(quiet,np.int32);core.sort_moves(bb,st,mb,moves,len(moves),0,quiet[-1],killers,core.HISTORY);assert moves[0]==quiet[-1]
    tested.append(b.fen())
from lab.perft import POSITIONS
for name,fen,expected in POSITIONS:assert core.perft_pos(from_fen(fen),3)==expected[3]
report=dict(pass_all=True,positions=len(tested),quiet_moves=count,max_logit_error=maxerr,cold_seconds=cold,perft_positions=len(POSITIONS),source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()},scope='ARM native/reference parity and ordering/perft; independent Linux deployment and equal-wall strength remain separate.')
(HERE/'policy-native-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'}))
