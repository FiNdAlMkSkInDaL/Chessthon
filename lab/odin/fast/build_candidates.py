"""Two bounded search experiments on the released Odin source, no fitted answers."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
base=ROOT/'odin_submission'
reports=[]
for name,safe in [('odin_v6_aspiration',False),('odin_v6_selective',True)]:
    out=ROOT/name;out.mkdir(exist_ok=False)
    for p in base.glob('*.py'):shutil.copy2(p,out/p.name)
    path=out/'core_nb.py';s=path.read_text(encoding='utf-8')
    start=s.index('        if aspiration_failed:\n',s.index('def search_root('))
    end=s.index('        dt = time.perf_counter() - now',start)
    s=s[:start]+'''        # Widen only the failed side before paying for a full-window search.
        window = ASPIRATION
        retries = 0
        while not aborted[0] and (score <= a or score >= b):
            retries += 1
            window *= 2
            if retries >= 4:
                a, b = -INF, INF
            elif score <= a:
                a = max(-INF, int(score) - window)
            else:
                b = min(INF, int(score) + window)
            retry_args = list(args)
            retry_args[9], retry_args[10] = a, b
            move, score = root_search_nb(*retry_args)
'''+s[end:]
    if safe:
        needle='            and has_nm_pieces(bb, np.int32(st[SIDE]))\n'
        assert s.count(needle)==1
        s=s.replace(needle,needle+'''            # Sparse minor/rook endings are the main zugzwang risk.
            and (bb[4] | bb[10] != 0 or
                 popc(bb[1] | bb[2] | bb[3] | bb[7] | bb[8] | bb[9]) >= 5)
''')
        needle='        move_history = histy[mover, m_to(move)] if quiet else 0\n'
        assert s.count(needle)==1
        s=s.replace(needle,needle+'''        critical_pawn = mover % 6 == 0 and (
            (mover == 0 and m_to(move) >= 40) or (mover == 6 and m_to(move) < 24)
        )
''')
        needle='            and depth <= FF_MAX_D\n'
        assert s.count(needle)==1
        s=s.replace(needle,'            and searched > 0\n            and not critical_pawn\n'+needle)
    path.write_text(s,encoding='utf-8',newline='\n')
    agent=out/'agent.py';s=agent.read_text(encoding='utf-8').replace('Odin v5.','Odin v6 development.');agent.write_text(s,encoding='utf-8',newline='\n')
    reports.append({'candidate':name,'features':['Directional exponentially widening aspiration']+(['Sparse null guard','Retain first move and advanced pawns in futility search'] if safe else []),
                    'gate':'Fast isolated-node paired screen vs Odin, native cold gate, then112 fresh full-clock games vs Odin.',
                    'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.py'))}})
(ROOT/'lab/odin/fast/candidates.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf-8')
print(json.dumps(reports))
