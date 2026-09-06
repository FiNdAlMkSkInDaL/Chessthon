"""Original non-mutating legality filter. Preserve exact generated move order."""
import argparse,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ROOT/'odin_fused');ap.add_argument('--output',type=Path,default=ROOT/'odin_direct_legal');args=ap.parse_args()
args.output.mkdir(exist_ok=False)
for p in args.source.glob('*.py'):shutil.copy2(p,args.output/p.name)
p=args.output/'core_nb.py';s=p.read_text(encoding='utf-8')
helpers='''@njit(cache=False)
def pinned_pieces_nb(bb, mb, st, king, us):
    """Own pieces whose departure could expose a slider attack on our king."""
    pinned = np.uint64(0)
    f0 = king & 7
    r0 = king >> 3
    for d in range(8):
        f = f0 + RAY_DF[d]
        r = r0 + RAY_DR[d]
        blocker = -1
        while 0 <= f < 8 and 0 <= r < 8:
            sq = r*8+f
            piece = np.int32(mb[sq])
            if piece >= 0:
                if blocker < 0:
                    if piece//6 != us:
                        break
                    blocker = sq
                else:
                    if piece//6 != us:
                        pt = piece%6
                        diagonal = RAY_DF[d] != 0 and RAY_DR[d] != 0
                        if pt == 4 or (pt == 2 and diagonal) or (pt == 3 and not diagonal):
                            pinned |= bit(blocker)
                    break
            f += RAY_DF[d]
            r += RAY_DR[d]
    return pinned


@njit(cache=False)
def move_safe_nb(bb, mb, st, move, king, checked, pinned):
    """Test attacks in the resulting occupancy without mutating game state.

    Pseudo-generator already checks castling origin/transit squares. Captured
    attackers must be removed from attack masks (especially EP checking pawns).
    EP bypasses the pin shortcut because two occupied squares disappear.
    """
    frm = m_from(move)
    to = m_to(move)
    us = np.int32(st[SIDE])
    mover = np.int32(mb[frm])
    is_king = mover%6 == 5
    ep = m_ep(move)
    if not checked and not is_king and not ep and not (pinned & bit(frm)):
        return True
    occ = (np.uint64(st[OCC]) & ~bit(frm)) | bit(to)
    captured = bit(to)
    if ep:
        captured = bit(to-8 if us == 0 else to+8)
        occ &= ~captured
    if m_castle(move):
        if to == 6:
            occ = (occ & ~bit(7)) | bit(5)
        elif to == 2:
            occ = (occ & ~bit(0)) | bit(3)
        elif to == 62:
            occ = (occ & ~bit(63)) | bit(61)
        else:
            occ = (occ & ~bit(56)) | bit(59)
    sq = to if is_king else king
    base = (us^1)*6
    surviving = ~captured
    if PAWN_A[us,sq] & bb[base] & surviving:
        return False
    if KNIGHT_A[sq] & bb[base+1] & surviving:
        return False
    if KING_A[sq] & bb[base+5] & surviving:
        return False
    if bishop_att(sq,occ) & (bb[base+2] | bb[base+4]) & surviving:
        return False
    if rook_att(sq,occ) & (bb[base+3] | bb[base+4]) & surviving:
        return False
    return True


'''
idx=s.index('@njit(cache=False)\ndef gen_legal(');s=s[:idx]+helpers+s[idx:]
for name in ('gen_legal','has_legal_nb','gen_noisy'):
    start=s.index('def '+name+'(');end=s.index('\n\n\n@njit',start);body=s[start:end]
    body=body.replace('    undo = np.zeros(7, dtype=np.uint64)\n','')
    anchor='    us = np.int32(st[SIDE])\n';assert body.count(anchor)==1
    body=body.replace(anchor,anchor+'    king = lsb(bb[us*6+5])\n    checked = in_check_nb(bb, st, us)\n    pinned = pinned_pieces_nb(bb, mb, st, king, us) if not checked else np.uint64(0)\n')
    if name=='has_legal_nb':
        old='        make_nb(bb, mb, st, mv, undo)\n        legal = not in_check_nb(bb, st, us)\n        unmake_nb(bb, mb, st, mv, undo)\n        if legal:'
        new='        if move_safe_nb(bb, mb, st, mv, king, checked, pinned):'
    else:
        old='        make_nb(bb, mb, st, mv, undo)\n        if not in_check_nb(bb, st, us):'
        new='        if move_safe_nb(bb, mb, st, mv, king, checked, pinned):'
        body=body.replace('        unmake_nb(bb, mb, st, mv, undo)\n','')
    assert body.count(old)==1;body=body.replace(old,new);s=s[:start]+body+s[end:]
p.write_text(s,encoding='utf-8',newline='\n')
print('Created direct legality candidate. Required gates: move-order parity, special-move state invariance, perft, fixed-node whole-search equivalence, native cold and speed, full-clock match.')
