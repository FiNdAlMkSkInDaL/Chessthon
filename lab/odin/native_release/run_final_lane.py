"""Execute one frozen primary lane then its original-Storm guard lane."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--validation-root',type=Path,required=True)
    ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--control',type=Path,required=True)
    ap.add_argument('--original-storm',type=Path,required=True)
    ap.add_argument('--lane',choices=('a','b'),required=True)
    ap.add_argument('--cpu',type=int,required=True)
    args = ap.parse_args()
    root = args.validation_root.resolve()
    sys.path.insert(0,str(root))
    from lab.odin.release.plan import digest,validate_plan
    plan_path = args.plan.resolve()
    plan = json.loads(plan_path.read_text())
    validate_plan(plan)
    frozen_hash = digest(plan_path)
    assert args.cpu == {'a':0,'b':1}[args.lane]
    for suite,baseline in [('primary',args.control),('guard',args.original_storm)]:
        assert digest(plan_path) == frozen_hash
        assert digest(args.candidate) == plan['suites'][suite]['candidate_sha256']
        assert digest(baseline) == plan['suites'][suite]['baseline_sha256']
        log = plan_path.parent/f'{suite}-{args.lane}.jsonl'
        assert not log.exists(), log
        command = [sys.executable,'-u','-m','lab.odin.release.linux_match',
                   '--validation-root',str(root),
                   '--harness-root',str(root/'lab/odin/official-harness-91f70e54'),
                   '--candidate',str(args.candidate.resolve()),'--baseline',str(baseline.resolve()),
                   '--openings',str(plan_path.parent/(suite+'.fen')),
                   '--cpu',str(args.cpu),'--plan',str(plan_path),'--suite',suite,'--lane',args.lane,
                   '--base-ms','120000','--increment-ms','500','--log',str(log)]
        print(json.dumps({'event':'SUITE_START','suite':suite,'lane':args.lane,'plan_sha256':frozen_hash}),flush=True)
        subprocess.run(command,cwd=root,check=True)
    print(json.dumps({'event':'LANE_COMPLETE','lane':args.lane,'plan_sha256':frozen_hash}),flush=True)


if __name__ == '__main__':
    main()
