"""All-material root preservation, boundaries and complete winning conversions."""
import collections,hashlib,json,random,sys,time
from pathlib import Path
import chess,chess.syzygy
HERE=Path(__file__).resolve().parent;source=HERE/'prototypes/tablebase';sys.path.insert(0,str(source))
t=time.perf_counter();import syzygy_root as policy
from endgame_exact import choose_exact
cold=time.perf_counter()-t
rng=random.Random(20260906)
manifest=json.loads((HERE/'tablebase-manifest.json').read_text())
for name,digest in manifest['files'].items():assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest
names=sorted(p.stem for p in (source/'syzygy').glob('*.rtbw'))
tb=policy._TABLEBASE
states=[];wins=[];timings=[];counts=collections.Counter()
def effective(b):
    if b.is_checkmate():return -2
    if b.is_stalemate() or b.is_insufficient_material() or b.halfmove_clock>=100:return 0
    w=tb.probe_wdl(b);d=tb.probe_dtz(b)
    return w if abs(w)==2 and b.halfmove_clock+abs(d)<=100 else 0
def test(b):
    before=(b.fen(),list(b.move_stack));value=effective(b);t=time.perf_counter();u=choose_exact(b);timings.append(time.perf_counter()-t)
    assert before==(b.fen(),list(b.move_stack)) and u is not None
    move=chess.Move.from_uci(u);assert move in b.legal_moves
    b.push(move);got=-effective(b);b.pop();assert got>=value,(b.fen(),u,value,got)
    return value
for name in names:
    pieces=[chess.Piece.from_symbol(p) for p in name.split('v')[0]]+[chess.Piece.from_symbol(p.lower()) for p in name.split('v')[1]]
    found=0
    for attempt in range(100000):
        b=chess.Board(None)
        for square,piece in zip(rng.sample(range(64),len(pieces)),pieces):b.set_piece_at(square,piece)
        b.turn=bool(rng.randrange(2))
        if not b.is_valid() or b.outcome() is not None:continue
        value=test(b);counts[name]+=1;states.append(b.fen());found+=1
        if value and len(wins)<160:wins.append(b.fen())
        mirror=b.mirror();assert effective(mirror)==value;test(mirror)
        boundary=b.copy();boundary.halfmove_clock=99;test(boundary)
        if found==24:break
    # Some material is always an automatic insufficient-material outcome.
    if found==0:assert name in ('KNvK','KBvK')
    else:assert found==24,(name,found)

# Promotion must avoid immediate stalemate; exact KPK permits the rook promotion.
b=chess.Board('8/k1P5/2K5/8/8/8/8/8 w - - 0 1');u=choose_exact(b);assert u=='c7c8r',(u,b.fen())
b=chess.Board('7k/8/8/3pP3/8/8/8/K7 w - d6 0 1');assert b.is_valid();test(b)
b=chess.Board('4k3/8/8/8/8/8/8/4K2R w K - 0 1');assert policy.choose_syzygy(b) is None
b=chess.Board('8/k1P5/2K5/8/8/8/8/8 w - - 0 201');assert policy.choose_syzygy(b) is None
saved=policy._TABLEBASE;policy._TABLEBASE=chess.syzygy.Tablebase()
try:assert policy.choose_syzygy(chess.Board(states[0])) is None
finally:policy._TABLEBASE.close();policy._TABLEBASE=saved

# A known child third occurrence is a draw even when its WDL is nonzero.
b=chess.Board(wins[0]);u=choose_exact(b);b.push_uci(u)
if not b.is_checkmate():assert policy.child_value(b,{b._transposition_key():2})[0]==0
b.pop()

rollouts=[]
for fen in wins[::2][:64]:
    b=chess.Board(fen);wdl=effective(b);winner=b.turn if wdl>0 else not b.turn
    seen=collections.Counter({b._transposition_key():1});plies=0
    while b.outcome() is None and not b.is_fifty_moves() and not b.is_repetition(3) and plies<300:
        before=b.fen();t=time.perf_counter();u=choose_exact(b,seen);timings.append(time.perf_counter()-t)
        assert u is not None and chess.Move.from_uci(u) in b.legal_moves
        b.push_uci(u);seen[b._transposition_key()]+=1;plies+=1
    result=b.outcome();assert result is not None and result.winner==winner,(fen,b.fen(),plies,result)
    rollouts.append(dict(fen=fen,plies=plies,result=result.result()))
result=dict(audit='PASS',families=dict(counts),random_positions=len(states),root_checks=len(timings),rollouts=rollouts,rollout_plies=sum(r['plies'] for r in rollouts),policy_import_seconds=cold,max_policy_ms=max(timings)*1000,
    total_uncompressed_bytes=manifest['total_uncompressed_bytes'],script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),manifest_sha256=hashlib.sha256((HERE/'tablebase-manifest.json').read_bytes()).hexdigest(),
    scope='Random all-material WDL/clock preservation and complete DTZ conversions, with original 3-piece DTM retained. Final 200 plies fall back to search. No full-history expanded proof or full-clock archive gate.')
(HERE/'tablebase-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('rollouts','families')}))
