"""Differential legality/perft against python-chess and original trial filter."""
import argparse,json,os,random,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ROOT/'odin_direct_legal');ap.add_argument('--cpu',type=int,default=6);ap.add_argument('--output',type=Path,default=ROOT/'lab/odin/fast/direct-legal-test.json');args=ap.parse_args()
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[name]='1'
sys.path.insert(0,str(ROOT))
if os.name=='nt':
    from lab.laptop_runner import apply_windows_affinity
    assert apply_windows_affinity(args.cpu)['applied']
else:os.sched_setaffinity(0,{args.cpu})
sys.path.insert(0,str(args.source.resolve()))
import chess,numpy as np
import core_nb as c
from board_nb import from_fen
from numba import njit

@njit(cache=False)
def old_legal(bb,mb,st,out,scratch):
    nps=c.gen_pseudo(bb,mb,st,scratch);us=np.int32(st[c.SIDE]);u=np.zeros(7,np.uint64);n=0
    for i in range(nps):
        mv=scratch[i];c.make_nb(bb,mb,st,mv,u)
        if not c.in_check_nb(bb,st,us):out[n]=mv;n+=1
        c.unmake_nb(bb,mb,st,mv,u)
    return n

def uci(m):
    return chess.square_name(int(c.m_from(m)))+chess.square_name(int(c.m_to(m)))+(' nbrq'[int(c.m_promo(m))] if c.m_promo(m) else '')

started=time.monotonic();boards=[]
for path in [ROOT/'lab/odin/quiet_eval/fit-records.jsonl',ROOT/'lab/odin/training/corpus-20k.jsonl']:
    rows=[json.loads(s) for s in path.read_text().splitlines()]
    boards.extend(chess.Board(r['fen']) for r in rows[::7])
special=[chess.STARTING_FEN,'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1',
         '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1',
         'r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1',
         'rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8',
         'r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10',
         '8/8/8/r4pPK/8/8/8/7k w - f6 0 1',
         '8/8/8/3pP3/4K3/8/8/k7 w - d6 0 1',
         '4k3/8/8/8/8/8/p7/1R2K3 b - - 0 1']
boards.extend(chess.Board(f) for f in special)
rng=random.Random(20260906)
for game in range(40):
    b=chess.Board(special[game%6])
    for ply in range(150):
        boards.append(b.copy(stack=False))
        moves=list(b.legal_moves)
        if not moves:break
        captures=[m for m in moves if b.is_capture(m) or m.promotion]
        b.push(rng.choice(captures if captures and rng.random()<.3 else moves))
counts={'positions':0,'legal_moves':0,'captures':0,'en_passant':0,'castles':0,'promotions':0,'checks':0}
for b in boards:
    assert b.is_valid(),b.fen()
    bb,mb,st=c.pack_pos(from_fen(b.fen()));before=[a.copy() for a in (bb,mb,st)]
    out=np.zeros(c.MAX_MOVES,np.int32);ref=out.copy();scratch=out.copy();u=np.zeros(7,np.uint64)
    n=c.gen_legal(bb,mb,st,out,scratch);nr=old_legal(bb,mb,st,ref,scratch)
    assert n==nr and np.array_equal(out[:n],ref[:nr]),b.fen()
    assert {uci(m) for m in out[:n]}=={m.uci() for m in b.legal_moves},b.fen()
    noisy=out.copy();nn=c.gen_noisy(bb,mb,st,noisy,scratch)
    assert list(noisy[:nn])==[m for m in ref[:nr] if c.m_cap(m) or c.m_promo(m)],b.fen()
    assert c.has_legal_nb(bb,mb,st,scratch,u)==bool(n),b.fen()
    if hasattr(c,'RAY_MASKS'):
        for packed in out[:n]:
            assert c.gives_check_nb(bb,mb,st,packed,u)==b.gives_check(chess.Move.from_uci(uci(packed))),(b.fen(),uci(packed))
    assert all(np.array_equal(a,z) for a,z in zip(before,(bb,mb,st))),b.fen()
    counts['positions']+=1;counts['legal_moves']+=n;counts['checks']+=b.is_check()
    for m in b.legal_moves:
        counts['captures']+=b.is_capture(m);counts['en_passant']+=b.is_en_passant(m);counts['castles']+=b.is_castling(m);counts['promotions']+=bool(m.promotion)
perft=[]
for fen,expected in zip(special[:6],[197281,4085603,43238,422333,2103487,3894594]):
    got=c.perft_pos(from_fen(fen),4);assert got==expected,(fen,got,expected)
    perft.append({'fen':fen,'depth':4,'nodes':int(got)})
result={'pass':True,'counts':counts,'perft':perft,'seconds':time.monotonic()-started,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.source.glob('*.py')}}
args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('source_hashes','perft')}),flush=True)
