"""Integrate only the low-cost, original learned zero-history tie breaker."""
import json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
r=json.loads((HERE/'policy-cheap/result.json').read_text());assert r['development_gate_pass']
source=HERE/'prototypes/policy_cheap';source.mkdir(exist_ok=False)
for p in (ROOT/'tempest_exact').iterdir():
    if p.is_file():(source/p.name).write_bytes(p.read_bytes())
fragment='''
# Original conditional move model trained offline, not a position/move table.
QUIET_PRIOR_W = np.array(WEIGHTS, dtype=np.float64)

@njit(cache=False, inline='never')
def quiet_prior_value_nb(bb, mb, st, move):
    frm=m_from(move); to=m_to(move); piece=np.int32(mb[frm]); pt=piece%6
    us=piece//6; base=us*6; enemy=(us^1)*6
    king=lsb(bb[base+5]); ek=lsb(bb[enemy+5]); phase=min(24,np.int64(st[PHASE_ACC]))
    w=QUIET_PRIOR_W[pt]
    value=w[0]
    value+=w[1]*((MG_T[piece,to]-MG_T[piece,frm])*phase+(EG_T[piece,to]-EG_T[piece,frm])*(24-phase))/2400.0
    value+=w[2]*int(bool(PAWN_A[us,frm]&bb[enemy]))
    value+=w[3]*int(bool(PAWN_A[us,to]&bb[enemy]))
    value+=w[4]*int(bool(PAWN_A[us^1,to]&bb[base]))
    value+=w[5]*int(bool(m_castle(move)))
    if pt==0:value+=w[6]*((to>>3)-(frm>>3))*(1 if us==0 else -1)
    value+=w[7]*(max(abs((frm&7)-(ek&7)),abs((frm>>3)-(ek>>3)))-max(abs((to&7)-(ek&7)),abs((to>>3)-(ek>>3))))
    if pt!=5:value+=w[8]*(max(abs((frm&7)-(king&7)),abs((frm>>3)-(king>>3)))-max(abs((to&7)-(king&7)),abs((to>>3)-(king>>3))))
    if pt==3 or pt==4:value+=w[9]*int((to&7)==(ek&7))
    if pt==0:value+=w[10]*int(abs((to&7)-(ek&7))<=1 and max(abs((to&7)-(ek&7)),abs((to>>3)-(ek>>3)))<=3 and bool(bb[base+4]))
    if pt==3:value+=w[11]*int(not bool((bb[base]|bb[enemy])&FEATURE_FILES[to&7]))
    value+=w[12]*(abs(2*(frm&7)-7)+abs(2*(frm>>3)-7)-abs(2*(to&7)-7)-abs(2*(to>>3)-7))/4.0
    return value

'''.replace('WEIGHTS',repr(r['collapsed_coefficients']))
p=source/'core_nb.py';s=p.read_text();anchor="@njit(cache=False)\ndef sort_moves(mb, moves, n, ply, hash_move, killers, histy):"
assert s.count(anchor)==1;s=s.replace(anchor,fragment+anchor.replace('sort_moves(mb,','sort_moves(bb, st, mb,'))
anchor='        a, b = order_key(mb, moves[i], ply, hash_move, killers, histy)'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'''
        if a==4:
            b*=1024
            if b==0:
                # Bound the prior so a nonzero history value always wins.
                b=-np.int32(max(-511,min(511,int(np.rint(64*quiet_prior_value_nb(bb,mb,st,moves[i]))))))
''')
assert s.count('sort_moves(mb,')==3;s=s.replace('sort_moves(mb,','sort_moves(bb, st, mb,')
p.write_text(s)
report=dict(model_sha256=hashlib.sha256((HERE/'policy-cheap/result.json').read_bytes()).hexdigest(),source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()},scope='Original learned tie-breaker only. No LMR/futility/evaluator/clock changes. Native parity, runtime and match gates required.')
(HERE/'policy-native-manifest.json').write_text(json.dumps(report,indent=2));print('Policy prototype staged')
