"""Build the audited confirmation winner with separately verified optimizations."""
import json,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
report=json.loads((HERE/'confirmation-report.json').read_text());assert report['complete']
name=report['ranking'][0];result=next(r for r in report['candidates'] if r['name']==name);assert result['score']>.5 and not result['errors']
policy=json.loads((HERE/'finalist-policy.json').read_text());job=next(j for j in policy['generation'] if j['name']==name)
source=ROOT/job['source'];out=ROOT/'odin_v6'
for filename in ('fused-benchmark.json','fused-search-benchmark.json','fused-search-benchmark-linux.json'):
    assert json.loads((HERE/filename).read_text())['pass']
subprocess.run([sys.executable,'-B',str(HERE/'build_fused.py'),'--source',str(source),'--output',str(out)],check=True)
p=out/'core_nb.py';s=p.read_text(encoding='utf-8');features=['Fused original positional evaluation']
if 'def sort_moves(bb, mb, st,' in s:
    for filename in ('see-bound-test.json','see-promotion-bound-test.json','see-search-benchmark.json'):
        assert json.loads((HERE/filename).read_text())['pass']
    fast=(ROOT/'odin_see_fast/core_nb.py').read_text(encoding='utf-8')
    a=fast.index('def sort_moves(');b=fast.index('\n\n\n@njit',a);replacement=fast[a:b]
    a=s.index('def sort_moves(');b=s.index('\n\n\n@njit',a);s=s[:a]+replacement+s[b:]
    features.append('Equivalent sign-bound fast capture ordering')
p.write_text(s,encoding='utf-8',newline='\n')
agent=out/'agent.py';s=agent.read_text(encoding='utf-8');start=s.index('# Odin generation ');end=s.index('\n',start)
s=s[:start]+'# Odin v6. Original selective search and optimized positional evaluation.'+s[end:];agent.write_text(s,encoding='utf-8',newline='\n')
manifest={'selected':name,'source':job['source'],'confirmation':result,'optimizations':features,
          'confirmation_report_sha256':hashlib.sha256((HERE/'confirmation-report.json').read_bytes()).hexdigest(),
          'unoptimized_hashes':job['hashes'],'final_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.py'))},
          'required_before_overnight':'Native exact-source gate and Linux paired whole-search equivalence/throughput vs unoptimized winner. Then freeze112 games against released v5. Do not promote automatically.'}
(HERE/'winner-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))
