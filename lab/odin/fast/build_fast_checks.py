"""Non-mutating check detection and ray-based pin detection, original code."""
import argparse,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ROOT/'odin_ray_core');ap.add_argument('--output',type=Path,default=ROOT/'odin_fast_checks');args=ap.parse_args()
args.output.mkdir(exist_ok=False)
for p in args.source.glob('*.py'):shutil.copy2(p,args.output/p.name)
p=args.output/'core_nb.py';s=p.read_text(encoding='utf-8')
start=s.index('def pinned_pieces_nb(');end=s.index('\n\n\n@njit',start)
s=s[:start]+'''def pinned_pieces_nb(bb, mb, st, king, us):
    pinned = np.uint64(0)
    ours = st[OCC_W] if us == 0 else st[OCC_B]
    base = (us^1)*6
    for d in range(8):
        blockers = RAY_MASKS[king,d] & st[OCC]
        if not blockers:
            continue
        first = lsb(blockers) if RAY_INCREASING[d] else msb(blockers)
        if not (bit(first) & ours):
            continue
        beyond = RAY_MASKS[first,d] & st[OCC]
        if not beyond:
            continue
        second = lsb(beyond) if RAY_INCREASING[d] else msb(beyond)
        sliders = (bb[base+3] | bb[base+4]) if d < 4 else (bb[base+2] | bb[base+4])
        if sliders & bit(second):
            pinned |= bit(first)
    return pinned'''+s[end:]
start=s.index('def gives_check_nb(');end=s.index('\n\n\n@njit',start)
s=s[:start]+'''def gives_check_nb(bb, mb, st, move, undo):
    """Our attack masks after a legal move; no hash/evaluation make/unmake."""
    us = np.int32(st[SIDE])
    base = us*6
    enemy_king = bb[(us^1)*6+5]
    if enemy_king == 0:
        return False
    king = lsb(enemy_king)
    frm = m_from(move)
    to = m_to(move)
    from_bit = bit(frm)
    to_bit = bit(to)
    occ = (st[OCC] & ~from_bit) | to_bit
    pawns = bb[base] & ~from_bit
    knights = bb[base+1] & ~from_bit
    bishops = bb[base+2] & ~from_bit
    rooks = bb[base+3] & ~from_bit
    queens = bb[base+4] & ~from_bit
    kings = bb[base+5] & ~from_bit
    pt = m_promo(move) if m_promo(move) else np.int32(mb[frm])%6
    if pt == 0: pawns |= to_bit
    elif pt == 1: knights |= to_bit
    elif pt == 2: bishops |= to_bit
    elif pt == 3: rooks |= to_bit
    elif pt == 4: queens |= to_bit
    else: kings |= to_bit
    if m_ep(move):
        occ &= ~bit(to-8 if us == 0 else to+8)
    if m_castle(move):
        rf = 7 if to == 6 else 0 if to == 2 else 63 if to == 62 else 56
        rt = 5 if to == 6 else 3 if to == 2 else 61 if to == 62 else 59
        rooks = (rooks & ~bit(rf)) | bit(rt)
        occ = (occ & ~bit(rf)) | bit(rt)
    if PAWN_A[us^1,king] & pawns: return True
    if KNIGHT_A[king] & knights: return True
    if KING_A[king] & kings: return True
    if bishop_att(king,occ) & (bishops | queens): return True
    if rook_att(king,occ) & (rooks | queens): return True
    return False'''+s[end:]
p.write_text(s,encoding='utf-8',newline='\n')
print('Created non-mutating check and ray-pin candidate. Require all legal check flags against python-chess, whole-search parity and native throughput.')
