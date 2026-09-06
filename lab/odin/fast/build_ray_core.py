"""Direct noisy generation and computed ray masks; no magic tables or code port."""
import argparse,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ROOT/'odin_direct_legal');ap.add_argument('--output',type=Path,default=ROOT/'odin_ray_core');ap.add_argument('--no-rays',action='store_true');args=ap.parse_args()
args.output.mkdir(exist_ok=False)
for p in args.source.glob('*.py'):shutil.copy2(p,args.output/p.name)
p=args.output/'core_nb.py';s=p.read_text(encoding='utf-8')
start=s.index('def gen_pseudo(');end=s.index('\n\n\n@njit',start)
noisy=s[start:end].replace('def gen_pseudo(','def gen_pseudo_noisy(')
old='''            else:
                out[n] = pack_move(frm, to, 0, False, False, False, False)
                n += 1
                if (frm >> 3) == start_rank:
                    to2 = frm + 2 * push
                    if empty & bit(to2):
                        out[n] = pack_move(frm, to2, 0, False, False, False, True)
                        n += 1
'''
assert noisy.count(old)==1;noisy=noisy.replace(old,'').replace(' & ~ours',' & theirs')
old='        n = gen_castles(bb, mb, st, out, n, us, frm, occ)\n';assert noisy.count(old)==1;noisy=noisy.replace(old,'')
s=s[:end]+'\n\n\n@njit(cache=False)\n'+noisy+s[end:]
start=s.index('def gen_noisy(');end=s.index('\n\n\n@njit',start);body=s[start:end]
assert body.count('gen_pseudo(')==1;body=body.replace('gen_pseudo(','gen_pseudo_noisy(')
s=s[:start]+body+s[end:]
if not args.no_rays:
    s=s.replace('from bitops_nb import lsb','from bitops_nb import lsb, msb')
    anchor='BISHOP_DI = np.array(BISHOP_DIR_I, dtype=np.int32)\n';assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'''# Geometry only: rays computed from our existing direction definitions at import.
RAY_MASKS = np.zeros((64,8),dtype=np.uint64)
for _sq in range(64):
    for _di, (_df,_dr) in enumerate(RAY_DIRS):
        _f,_r=(_sq&7)+_df,(_sq>>3)+_dr
        _mask=0
        while 0<=_f<8 and 0<=_r<8:
            _mask |= 1<<(_r*8+_f)
            _f+=_df;_r+=_dr
        RAY_MASKS[_sq,_di]=np.uint64(_mask)
RAY_INCREASING=np.array([dr*8+df>0 for df,dr in RAY_DIRS],dtype=np.bool_)
''')
    start=s.index('def sliding(');end=s.index('\n\n\n@njit',start)
    s=s[:start]+'''def sliding(sq, occ, dirs):
    attacks = np.uint64(0)
    for i in range(dirs.shape[0]):
        d = dirs[i]
        ray = RAY_MASKS[sq,d]
        blockers = ray & np.uint64(occ)
        if blockers:
            nearest = lsb(blockers) if RAY_INCREASING[d] else msb(blockers)
            ray ^= RAY_MASKS[nearest,d]
        attacks |= ray
    return attacks'''+s[end:]
    b=args.output/'bitops_nb.py'
    with b.open('a',encoding='utf-8',newline='\n') as f:f.write('''

@intrinsic
def _msb_u64(typing_context, value_type):
    if value_type != types.uint64:
        return None

    def codegen(context, builder, signature, args):
        # OR bit zero gives defined msb(0)==0, without changing nonzero inputs.
        nonzero = builder.or_(args[0], ir.Constant(ir.IntType(64), 1))
        leading = builder.ctlz(nonzero, ir.Constant(ir.IntType(1), 1))
        return builder.sub(ir.Constant(ir.IntType(64), 63), leading)

    return types.int64(types.uint64), codegen


@njit(cache=False, inline="always")
def msb(bb):
    return _msb_u64(np.uint64(bb))
''')
p.write_text(s,encoding='utf-8',newline='\n')
print('Created capture-only generator'+(' and first-blocker ray masks' if not args.no_rays else '')+'. Gates: exhaustive ray occupancies, legality/perft and whole-search parity, native throughput and cold init.')
