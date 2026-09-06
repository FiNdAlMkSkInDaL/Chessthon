"""Freeze final match inputs before the first holdout game; refuses replacement."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.odin.release.plan import digest, source_provenance, validate_plan

ORIGINAL_STORM = '15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c'
CONTROL = '35c6a33fed2e81acead145de53639ce516b1d24a6701a89a8c5fff81a582baf1'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--control', type=Path, required=True)
    ap.add_argument('--original-storm', type=Path, required=True)
    ap.add_argument('--output-directory', type=Path, required=True)
    args = ap.parse_args()
    assert digest(args.control) == CONTROL
    assert digest(args.original_storm) == ORIGINAL_STORM
    out = args.output_directory.resolve()
    out.mkdir(exist_ok=False)
    corpus = ROOT/'lab/odin/release_openings'
    manifest = json.loads((corpus/'manifest.json').read_text(encoding='utf-8'))
    fens = [s for s in (corpus/'holdout.fen').read_text().splitlines() if s.strip() and not s.startswith('#')]
    assert len(fens) == 40
    assert digest(corpus/'holdout.fen') == '21263a9007839774d18b0364a4a06410459399dd5794f2e5af225b20350d9cf1'
    guard_indices = manifest['guard_holdout_indices']
    assert guard_indices == [0,1,2,3,4,5,6,7,8,11,12,13,14,18,19,20]
    guard = [fens[i] for i in guard_indices]
    (out/'primary.fen').write_bytes((corpus/'holdout.fen').read_bytes())
    (out/'guard.fen').write_text('\n'.join(guard)+'\n', encoding='utf-8', newline='\n')
    candidate = digest(args.candidate)
    def suite(name, baseline, openings, criterion):
        return {'candidate_sha256': candidate, 'baseline_sha256': baseline,
                'openings_sha256': digest(out/(name+'.fen')), 'openings': openings,
                'min_pairs': len(openings), 'threshold': .5, 'criterion': criterion,
                'lanes': [{'id': lane, 'cpu': cpu, 'opening_indices': list(range(cpu,len(openings),2))}
                          for lane,cpu in [('a',0),('b',1)]]}
    plan = {'schema_version': 1, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
            'candidate_name': 'Odin', 'base_ms': 120000, 'increment_ms': 500,
            'init_budget_s': 90.0, 'ply_cap': 600,
            'packages': {'chess':'1.11.2','numpy':'2.5.2','numba':'0.67.0','llvmlite':'0.49.0'},
            'official_harness_commit': '91f70e54be07e1bf56311962044a08b822c3af50',
            'source_provenance': source_provenance(ROOT,ROOT/'lab/odin/official-harness-91f70e54'),
            'opening_manifest_sha256': digest(corpus/'manifest.json'),
            'guard_original_holdout_indices': guard_indices,
            'policy': 'Complete both fixed suites without changing candidate, control, starts, clocks or sample size. Any operational fault rejects promotion. Development results and guard games are never pooled into the primary confidence interval.',
            'suites': {'primary': suite('primary',CONTROL,fens,'paired_ci_lower'),
                       'guard': suite('guard',ORIGINAL_STORM,guard,'raw_score')}}
    validate_plan(plan)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'plan_sha256': digest(out/'plan.json'), 'candidate_sha256': candidate,
                      'games':112, 'output':str(out)}))


if __name__ == '__main__':
    main()
