"""Freeze paired equal-wall development matches with existing audited workers."""
import argparse,json,shutil,zipfile,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--name',required=True);ap.add_argument('--ms',type=int,default=500);ap.add_argument('--single-cpu',type=int,choices=(0,1));a=ap.parse_args()
dest=HERE/a.name;dest.mkdir(exist_ok=False);sources=[a.candidate.resolve(),a.baseline.resolve()]
for name in ('clock_match.py','clock_worker.py'):shutil.copyfile(ROOT/'lab/tempest_build/exact-match'/name,dest/name)
openings=ROOT/'lab/odin/fast/generation-openings/screen.fen'
plan=dict(pairs=8,games=16,think_ms=a.ms,indices=list(range(8)),candidate=str(sources[0].relative_to(ROOT)),baseline=str(sources[1].relative_to(ROOT)),sources={str(s.relative_to(ROOT)):{p.name:sha(p) for p in s.iterdir() if p.is_file() and p.suffix in ('.py','.npz')} for s in sources},opening_sha256=sha(openings),scope='Used-development equal-wall screen, no competition-clock or independent Elo claim. Complete all16 regardless of score. One active mover per assigned CPU; two paired workers within1800MB service. No shared mutable state between games.',decision='Below50% rejects this candidate for promotion;50-60% inconclusive;at least60% permits independent confirmation only after protocol/runtime gates.')
plan['lanes']=2 if a.single_cpu is None else 1
(dest/'plan.json').write_text(json.dumps(plan,indent=2));commands=[]
for cpu in ((0,1) if a.single_cpu is None else (a.single_cpu,)):
    indices=range(cpu*4,(cpu+1)*4) if a.single_cpu is None else range(8)
    command=f'lab/agamemnon_scale/{a.name}/clock_match.py --candidate {sources[0].relative_to(ROOT).as_posix()} --baseline {sources[1].relative_to(ROOT).as_posix()} --cpu {cpu} --think-ms {a.ms} --indices '+','.join(map(str,indices))+f' --openings lab/odin/fast/generation-openings/screen.fen --output lab/agamemnon_scale/{a.name}/lane{cpu}.jsonl'
    commands.append(command)
(dest/'commands.json').write_text(json.dumps(commands))
files=[openings,ROOT/'lab/laptop_runner.py',*dest.iterdir()]
for s in sources:files += [p for p in s.iterdir() if p.is_file() and p.suffix in ('.py','.npz')]
with zipfile.ZipFile(dest/'transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(ROOT).as_posix())
print(json.dumps(dict(name=a.name,commands=commands)))
