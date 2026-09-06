"""Skip sign-only SEE when the first exchange already bounds it nonnegative."""
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];out=ROOT/'odin_see_fast';out.mkdir(exist_ok=False)
for p in (ROOT/'odin_generation/see_order').glob('*.py'):shutil.copy2(p,out/p.name)
p=out/'core_nb.py';s=p.read_text(encoding='utf-8')
old='        if a == 1 and m_cap(moves[i]) and not m_promo(moves[i]) and see_nb(bb, mb, st, moves[i]) < 0:\n            a = 5  # Search losing captures after useful quiet moves.\n'
new='''        if a == 1 and m_cap(moves[i]) and not m_promo(moves[i]):
            to = m_to(moves[i])
            attacker = np.int32(mb[m_from(moves[i])]) % 6
            # Recapture can cost at most our capturing piece, unless an
            # enemy pawn can promote on the destination's back rank.
            uncertain = (SEE_V[victim_pt(mb, moves[i])] < SEE_V[attacker]
                         or to < 8 or to >= 56)
            if uncertain and see_nb(bb, mb, st, moves[i]) < 0:
                a = 5
'''
assert s.count(old)==1;s=s.replace(old,new);p.write_text(s,encoding='utf-8',newline='\n')
print('Created equivalent sign-bound capture ordering; excludes all back-rank promotion-recapture cases.')
