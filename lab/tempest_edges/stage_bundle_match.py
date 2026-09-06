"""Freeze one paired equal-wall addition-versus-current-stack screen."""
import argparse,hashlib,json,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True);ap.add_argument('--baseline',default='control');ap.add_argument('--name',required=True);ap.add_argument('--cpu',type=int,required=True);a=ap.parse_args()
assert all(x.replace('_','').replace('-','').isalnum() for x in (a.variant,a.baseline,a.name))
out=HERE/a.name;out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources=[f'lab/tempest_edges/prototypes/{a.variant}',f'lab/tempest_edges/prototypes/{a.baseline}']
for name in ('clock_match.py','clock_worker.py'):(out/name).write_bytes((ROOT/'lab/tempest_build/exact-match'/name).read_bytes())
openings=ROOT/'lab/odin/fast/generation-openings/screen.fen'
plan=dict(games=16,pairs=8,indices=list(range(8)),think_ms=500,cpu=a.cpu,candidate=sources[0],baseline=sources[1],
    sources={d:{p.name:sha(p) for p in (ROOT/d).iterdir() if p.is_file() and p.suffix in ('.py','.npz')} for d in sources},
    opening_sha256=sha(openings),helpers_sha256={p.name:sha(p) for p in out.glob('*.py')},
    decision='Complete all 16 games regardless of score. Below 50% rejects further promotion testing; 50-60% inconclusive; at least 60% nominates confirmation. Used development families. No full-clock or Elo claim. All legal/reset/source/operational checks must pass.',
    comparison='Addition against the narrower lazy-predicate stack, unless baseline explicitly names a later frozen stack. Desktop Tempest r1 is a separate eventual promotion control.')
(out/'plan.json').write_text(json.dumps(plan,indent=2))
command=f'lab/tempest_edges/{a.name}/clock_match.py --candidate {sources[0]} --baseline {sources[1]} --cpu {a.cpu} --think-ms 500 --indices 0,1,2,3,4,5,6,7 --openings lab/odin/fast/generation-openings/screen.fen --output lab/tempest_edges/{a.name}/lane.jsonl'
(out/'command.txt').write_text(command)
launch=f'''#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-edges-bundles-r1"
"$HOME/chess-tk/.venv/bin/python" -B {command} > lab/tempest_edges/{a.name}/lane.stdout 2> lab/tempest_edges/{a.name}/lane.stderr
'''
(out/'launch.sh').write_text(launch,newline='\n')
paths=[openings,ROOT/'lab/laptop_runner.py',out/'plan.json',out/'launch.sh',out/'command.txt',*out.glob('*.py')]
for d in sources:paths += [p for p in (ROOT/d).rglob('*') if p.is_file() and p.suffix in ('.py','.npz','.rtbw','.rtbz')]
with zipfile.ZipFile(out/'transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
print(json.dumps(dict(match=a.name,command=command,transport_sha256=sha(out/'transport.zip'))))
