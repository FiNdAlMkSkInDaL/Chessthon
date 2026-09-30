"""Freeze the measured, semantically equivalent architecture as Odin v6 source."""
import ast,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
source=ROOT/'odin_fast_checks';target=ROOT/'odin_v6'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={p.name:sha(p) for p in source.glob('*.py')}
legal=json.loads((HERE/'fast-checks-test.json').read_text())
assert legal['pass'] and legal['source_hashes']==hashes
ray=json.loads((HERE/'ray-mask-test.json').read_text());assert ray['pass']
for name in ('bitops_nb.py',):assert ray['source_hashes'][name]==hashes[name]
bench=json.loads((HERE/'checks-mixed-benchmark-linux-r2.json').read_text())
assert bench['pass'] and bench['metadata']['fused']['source_hashes']==hashes
assert bench['nodes_per_position']==1000000 and bench['positions']>=30
assert bench['throughput_ratio']>=1.25 and bench['platform'].startswith('Linux-')
baseline={p.name:sha(p) for p in (ROOT/'odin_submission').glob('*.py')}
assert bench['metadata']['baseline']['source_hashes']==baseline
target.mkdir(exist_ok=False)
for p in source.glob('*.py'):shutil.copy2(p,target/p.name)
p=target/'agent.py';old=p.read_text();new=old.replace('# Odin v5. Storm-derived selective search with original offline-fitted\n# positional evaluation, legal SEE/EP and current 600-ply referee handling.',
'# Odin v6. Direct legality and check tests, capture-only quiescence generation,\n# first-blocker rays and fused evaluation; Odin v5 chess/search semantics.')
assert old!=new and ast.dump(ast.parse(old))==ast.dump(ast.parse(new));p.write_text(new,encoding='utf-8',newline='\n')
for p in target.glob('*.py'):assert ast.dump(ast.parse(p.read_text()))==ast.dump(ast.parse((source/p.name).read_text()))
manifest={'name':'Odin v6','source':target.relative_to(ROOT).as_posix(),'tested_source':source.relative_to(ROOT).as_posix(),'source_hashes':{p.name:sha(p) for p in target.glob('*.py')},'tested_hashes':hashes,
          'difference_from_tested':'Only agent.py version comment; every module AST identical. Final exact archive requires native gate and full112-clock match.',
          'whole_search_benchmark':{'sha256':sha(HERE/'checks-mixed-benchmark-linux-r2.json'),'positions':bench['positions'],'nodes_per_position':bench['nodes_per_position'],'throughput_ratio':bench['throughput_ratio']},
          'architecture':['Non-mutating legal move filtering with pin shortcuts and exact king/EP/castling occupancy','Capture/promotion-only pseudo generation in quiescence, original move order','Computed geometry ray masks with compiler bit scans; no magic or third-party engine tables','Non-mutating checking-move tests and first/second-blocker pin detection','Arithmetic-equivalent fused original fitted evaluation'],
          'strength_policy':'Choose on exact semantics and measured native throughput. Short equal-time games are development diagnostics. Only untouched112 full competition-clock games decide promotion; no automatic archive replacement.'}
(HERE/'architecture-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'source':'odin_v6','throughput_ratio':bench['throughput_ratio'],'ast_identical_to_measured':True}))
