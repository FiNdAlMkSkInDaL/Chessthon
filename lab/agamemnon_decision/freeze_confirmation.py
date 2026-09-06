"""Freeze24 independent current-clock games only after the exact archive gate."""
import argparse,importlib.metadata,json,sys
from datetime import datetime,timezone
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);args=ap.parse_args()
root=args.root.resolve();sys.path.insert(0,str(root))
from lab.odin.release.plan import digest,source_provenance,validate_plan
assert sys.platform=='linux' and sys.version_info[:2]==(3,12)
gate=json.loads((root/'native-gate.json').read_text())
candidate=root/'candidate-linux-x86.zip';baseline=root/'baseline-tempest.zip'
assert gate['verdict']=='PASS' and gate['archive']['sha256']==digest(candidate)
assert digest(candidate)=='a72338865851743b0f50ce2796c20eb3c3cc88f66c2e91c83e970e83fa36b58c'
assert digest(baseline)=='0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4'
out=root/'confirmation24';out.mkdir(exist_ok=False)
source=root/'lab/tempest/fresh-confirmation/openings.fen'
assert digest(source)=='be8f7b3b16954d103a7f013619f1b4e515d264d364ed1d7e9411cd17ddaa84da'
(out/'openings.fen').write_bytes(source.read_bytes())
fens=[s for s in source.read_text().splitlines() if s.strip() and not s.startswith('#')]
assert len(fens)==12
plan=dict(schema_version=1,frozen_utc=datetime.now(timezone.utc).isoformat(),candidate_name='Agamemnon replay25',baseline_name='Tempest r1',
    base_ms=120000,increment_ms=500,init_budget_s=90.0,ply_cap=600,
    packages={n:importlib.metadata.version(n) for n in ('chess','numpy','numba','llvmlite')},
    source_provenance=source_provenance(root,root/'lab/tempest_build/official-284724ab'),
    policy='All24 current-clock games,12 unused confirmation families, complete pairs, no result-dependent stopping, zero faults. Paired95% lower score>50% and raw score>=55% target. Not the112-game release guard; no automatic promotion.',
    suites={'confirmation':dict(candidate_sha256=digest(candidate),baseline_sha256=digest(baseline),
        openings_sha256=digest(out/'openings.fen'),openings=fens,min_pairs=12,threshold=.5,criterion='paired_ci_lower',
        lanes=[dict(id=lane,cpu=cpu,opening_indices=list(range(cpu,12,2))) for lane,cpu in (('a',0),('b',1))])})
validate_plan(plan);(out/'plan.json').write_text(json.dumps(plan,indent=2))
print(json.dumps(dict(games=24,plan_sha256=digest(out/'plan.json'))))
