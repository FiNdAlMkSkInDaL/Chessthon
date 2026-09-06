"""Search and TT-continuation diagnostics; source isolated from Desktop release.

TT continuations after an aborted iteration are not certified completed PVs.
Record bounds/depths explicitly; reference-check their choices separately.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import sys,json,hashlib,inspect,time,argparse
from pathlib import Path
import numpy as np,chess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from lab.laptop_runner import apply_windows_affinity

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['baseline','cap1600','pressure8','pawn_threat','pawn_lmr','pawn_ff'],required=True);ap.add_argument('--cpu',type=int,default=2);ap.add_argument('--cases',type=Path);ap.add_argument('--tag',default='r2');ap.add_argument('--wall',action='store_true');a=ap.parse_args()
    if os.name=='nt':assert apply_windows_affinity(a.cpu)['applied']
    source=HERE/'prototypes'/a.variant;existed=source.exists();source.mkdir(parents=True,exist_ok=True)
    for p in (ROOT/'tempest_exact').iterdir():
        if p.is_file() and not existed:(source/p.name).write_bytes(p.read_bytes())
    corefile=source/'core_nb.py';s=(ROOT/'tempest_exact/core_nb.py').read_text()
    if a.variant in ('cap1600','pressure8'):
        old='return max(-400,min(400,score))';assert s.count(old)==1;s=s.replace(old,'return max(-1600,min(1600,score))')
    if a.variant=='pressure8':
        old='(sign*pressure*min(3,attackers)) * (2)';assert s.count(old)==2;s=s.replace(old,'(sign*pressure*min(3,attackers)) * (8)')
    if a.variant in ('pawn_threat','pawn_lmr','pawn_ff'):
        anchor='        move_history = histy[mover, m_to(move)] if quiet else 0'
        assert s.count(anchor)==1
        s=s.replace(anchor,anchor+'''
        # A quiet pawn push near the enemy king may open a forcing attack.
        # Preserve depth for this geometric class; no forced extension and
        # no reference move/FEN special cases.
        pawn_threat = False
        if quiet and mover % 6 == 0:
            ek = lsb(bb[(1 - mover // 6)*6+5])
            target = m_to(move)
            pawn_threat = abs((target&7)-(ek&7)) <= 1 and abs((target>>3)-(ek>>3)) <= 3
''')
        if a.variant!='pawn_lmr':
            old='            and quiet\n            and depth <= FF_MAX_D';assert s.count(old)==1;s=s.replace(old,'            and quiet\n            and not pawn_threat\n            and depth <= FF_MAX_D')
        if a.variant!='pawn_ff':
            old='            and not advanced_pawn';assert s.count(old)==1;s=s.replace(old,old+'\n            and not pawn_threat')
    if existed:assert corefile.read_text()==s
    elif a.variant!='baseline':corefile.write_text(s)
    source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
    sys.path.insert(0,str(source));t=time.perf_counter()
    import agent,core_nb as core,history
    from board_nb import from_fen,move_uci
    from movegen_nb import generate_legal
    assert core.NUMBA_READY; cold=time.perf_counter()-t
    snap={k:v.copy() for k,v in vars(core).items() if isinstance(v,np.ndarray) and v.flags.writeable}
    wall_driver=core.search_root;original=inspect.getsource(core.search_root)
    fixed=original.replace('nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)','nodes[1] = 0').replace('max_nodes = 10**15  # deadline inside compiled search is authoritative','max_nodes = _LAB_NODE_LIMIT')
    assert fixed!=original;exec(compile(fixed,'<attack-fixed-nodes>','exec'),core.__dict__)
    driver=core.search_root
    force=fixed.replace('root_moves=nroot','root_moves=max(2,nroot)')
    exec(compile(force,'<attack-forced-nodes>','exec'),core.__dict__);forced_driver=core.search_root
    if a.cases:cases=json.loads(a.cases.read_text())
    else:
        cases=json.loads((ROOT/'lab/tempest_build/day3-v6/round37-probe-cases.json').read_text())+json.loads((ROOT/'lab/tempest_build/day3-v6/round37-opponent-case.json').read_text())
        # Additional diagnostics from earlier losses, never used for fitting.
        old=json.loads((ROOT/'lab/tempest/corpus-v1.json').read_text())
        cases += [c for c in old if c['source_kind']=='own-known']
    def reset(c):
        for k,v in snap.items():np.copyto(getattr(core,k),v)
        history.reset();b=chess.Board(c['start_fen']);own=c['storm_colour']=='white'
        for u in c['history_uci']:
            if b.turn==own:history.observe_served(b);history.observe_our_uci(b,u)
            b.push_uci(u)
        assert b.fen()==c['fen'];history.observe_served(b);return b
    def run(c,budget,wall=False):
        b=reset(c);pos=from_fen(b.fen(en_passant='fen'));core._LAB_NODE_LIMIT=budget;t=time.perf_counter()
        roots=generate_legal(pos)
        if c.get('restrict'):roots=[m for m in roots if move_uci(m)==c['restrict']]
        selected_driver=wall_driver if wall else forced_driver if c.get('restrict') else driver
        assert not (wall and c.get('restrict'))
        m=selected_driver(pos,roots,budget if wall else 1e12,budget if wall else 1e12,False,history.zkeys().copy());elapsed=time.perf_counter()-t
        info=core.last_info().copy();u=move_uci(m);assert chess.Move.from_uci(u) in b.legal_moves
        trace=[];seen=set()
        for ply in range(17):
            p=from_fen(b.fen(en_passant='fen'));bb,mb,st=core.pack_pos(p)
            k=core.cap_tt_key(st[core.KEY],max(0,600-b.ply()))
            hit,tm,d,flag,score=core.tt_probe(np.uint64(k),ply,core.TT_KEY,core.TT_MOVE,core.TT_SCORE,core.TT_DEPTH,core.TT_GEN)
            nxt=u if ply==0 else move_uci(tm) if hit and tm else None
            trace.append(dict(ply=ply,fen=b.fen(),next_uci=nxt,static_white=int(core.evaluate_nb(bb,st,False))*(1 if b.turn else -1),correction_white=int(core.positional_correction_nb(bb,st)),tt_hit=bool(hit),tt_depth=int(d),tt_flag=int(flag),tt_score_stm=int(score)))
            if not nxt or chess.Move.from_uci(nxt) not in b.legal_moves or b.is_game_over():break
            key=tuple(b._transposition_key())
            if key in seen:break
            seen.add(key);b.push_uci(nxt)
        return dict(id=c['id'],budget=budget,mode='wall' if wall else 'nodes',uci=u,info=info,seconds=elapsed,trace=trace)
    out=HERE/(a.variant+'-trace-'+a.tag+'.jsonl')
    with out.open('x') as f:
        def emit(r):f.write(json.dumps(r)+'\n');f.flush()
        emit(dict(type='metadata',source_hashes=source_hashes,cold_seconds=cold,driver_sha256=hashlib.sha256(fixed.encode()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Development diagnostics only; TT lines include aborted-iteration entries'))
        x=run(cases[0],20000);run(cases[-1],20000);y=run(cases[0],20000)
        assert (x['uci'],x['info']['score'],x['info']['nodes'])==(y['uci'],y['info']['score'],y['info']['nodes']);emit(dict(type='isolation',pass_ABA=True))
        for c in cases:
            for budget in ([1500] if a.wall else c.get('budgets',([200000,1000000] if c in cases[:4] else [200000]))):
                r=run(c,budget,a.wall);emit(dict(type='probe',**r));print(a.variant,c['id'],budget,r['uci'],r['info']['score'],flush=True)
        emit(dict(type='complete',source_unchanged=source_hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}))
if __name__=='__main__':main()
