"""Freeze 16 equal-wall development games; no outcome-based stopping."""
import json,hashlib,zipfile,argparse
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--name',default='match');ap.add_argument('--variant',default='pawn_threat');ap.add_argument('--think-ms',type=int,default=100);ap.add_argument('--remote',default='tempest-attack-r1');args=ap.parse_args()
assert args.variant in ('pawn_threat','pawn_lmr','policy_cheap') and args.name in ('match','match-lmr','match-policy') and args.remote in ('tempest-attack-r1','tempest-attack-lmr-r1','tempest-policy-r1')
out=HERE/args.name;out.mkdir(exist_ok=False)
sources=['lab/tempest_attack/prototypes/'+args.variant,'tempest_exact']
for name in ('clock_match.py','clock_worker.py'):
    (out/name).write_bytes((ROOT/'lab/tempest_build/exact-match'/name).read_bytes())
openings=ROOT/'lab/odin/fast/generation-openings/screen.fen'
plan=dict(games=16,pairs=8,indices=list(range(8)),think_ms=args.think_ms,
 candidate=sources[0],baseline=sources[1],
 sources={d:{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/d).iterdir() if p.is_file() and p.suffix in ('.py','.npz')} for d in sources},
 opening_sha256=hashlib.sha256(openings.read_bytes()).hexdigest(),
 decision='Complete all 16 games regardless of results. Score below 50% rejects further promotion testing; at least 60% merits independent confirmation. Intermediate scores are inconclusive. Zero operational/source/reset/legal failures required. No full-clock or Elo claim.',
 selection='Pawn-threat preservation nominated by selected development diagnostics. Openings are already-used development families, not independent confirmation.',
 referee='current actual repetition/fifty and 600 absolute plies, pinned official 284724ab56cecb2a1a9a4e5769b4748adab4ed90',
 helpers_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.py')})
if args.variant=='policy_cheap':
    assert json.loads((HERE/'policy-native-verification.json').read_text())['pass_all']
    plan['selection']='Original quiet-move policy nominated by used-family ranking CV, then native reference/priority/perft checks. No site-position labels were used to fit the model. This development match cannot establish Elo.'
    plan['model_sha256']=hashlib.sha256((HERE/'policy-cheap/result.json').read_bytes()).hexdigest()
(out/'plan.json').write_text(json.dumps(plan,indent=2))
launch='''#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-attack-r1"
PY="$HOME/chess-tk/.venv/bin/python"
"$PY" -B lab/tempest_attack/match/clock_match.py --candidate lab/tempest_attack/prototypes/pawn_threat --baseline tempest_exact --cpu 0 --think-ms 100 --indices 0,1,2,3 --openings lab/odin/fast/generation-openings/screen.fen --output lab/tempest_attack/match/lane-a.jsonl > lab/tempest_attack/match/lane-a.stdout 2> lab/tempest_attack/match/lane-a.stderr &
A=$!
"$PY" -B lab/tempest_attack/match/clock_match.py --candidate lab/tempest_attack/prototypes/pawn_threat --baseline tempest_exact --cpu 1 --think-ms 100 --indices 4,5,6,7 --openings lab/odin/fast/generation-openings/screen.fen --output lab/tempest_attack/match/lane-b.jsonl > lab/tempest_attack/match/lane-b.stdout 2> lab/tempest_attack/match/lane-b.stderr &
B=$!
wait "$A"
wait "$B"
'''
launch=launch.replace('tempest-attack-r1',args.remote).replace('/match/','/'+args.name+'/').replace('prototypes/pawn_threat','prototypes/'+args.variant).replace('--think-ms 100','--think-ms '+str(args.think_ms))
(out/'launch.sh').write_text(launch,newline='\n')
paths=[openings,ROOT/'lab/laptop_runner.py',*out.glob('*.py'),out/'plan.json',out/'launch.sh']
for d in sources:paths += [p for p in (ROOT/d).iterdir() if p.is_file() and p.suffix in ('.py','.npz')]
with zipfile.ZipFile(out/'transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
print(json.dumps(dict(games=16,transport_sha256=hashlib.sha256((out/'transport.zip').read_bytes()).hexdigest())))
