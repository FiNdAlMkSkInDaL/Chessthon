"""Predeclared ablation: retain selective safeguards, restore released aspiration."""
import json,shutil,hashlib,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
out=ROOT/'odin_v6_guards';out.mkdir(exist_ok=False)
for p in (ROOT/'odin_v6_selective').glob('*.py'):shutil.copy2(p,out/p.name)
base=(ROOT/'odin_submission/core_nb.py').read_text(encoding='utf-8')
original=base[base.index('        if aspiration_failed:\n',base.index('def search_root(')):base.index('        dt = time.perf_counter() - now',base.index('def search_root('))]
p=out/'core_nb.py';s=p.read_text(encoding='utf-8');start=s.index('        # Widen only the failed side');end=s.index('        dt = time.perf_counter() - now',start)
s=s[:start]+original+s[end:];p.write_text(s,encoding='utf-8',newline='\n')
policy={'candidate':'odin_v6_guards','features':['Sparse null guard','Retain first move and advanced pawns in futility search'],'node_limit':20000,'pairs':24,
        'reason':'Aspiration-only regressed; cautious-pruning combination52.083% in completed48-game screen. Test removal of aspiration using the same development pairs. These are now reused development data, never independent confirmation.',
        'selection':'Complete48 games. Prefer guards if its score is at least the selective combination25/48 and there are zero faults; otherwise retain selective. Gate selected exact source natively then112 untouched full-clock games. No confidence claim for selecting among three candidates.',
        'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.py'))}}
(HERE/'guards-policy.json').write_text(json.dumps(policy,indent=2)+'\n')
with zipfile.ZipFile(HERE/'guards-transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in out.glob('*.py'):z.write(p,p.relative_to(ROOT).as_posix())
    z.write(HERE/'guards-policy.json','lab/odin/fast/guards-policy.json')
print(json.dumps(policy))
