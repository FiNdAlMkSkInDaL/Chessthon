"""Freeze112 new full-clock games against released Odin v5, before play."""
import argparse,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.odin.release.plan import digest,source_provenance,validate_plan
BASELINE='c7d8972e823eb821c016010445d4b02996daff954d870d63083c445850e21102'
ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--openings',type=Path,required=True);ap.add_argument('--output-directory',type=Path,required=True);args=ap.parse_args()
assert digest(args.baseline)==BASELINE
assert digest(args.openings)=='a2a8f62cadf481adacbb101f87c34a6e7c7125569f49d1bfe672e2bbfe6fea67'
fens=[s for s in args.openings.read_text().splitlines() if s.strip() and not s.startswith('#')];assert len(fens)==56
out=args.output_directory.resolve();out.mkdir(exist_ok=False)
(out/'primary.fen').write_bytes(args.openings.read_bytes())
plan={'schema_version':1,'frozen_utc':datetime.now(timezone.utc).isoformat(),'candidate_name':'Odin v6','baseline_name':'Odin v5 released',
      'base_ms':120000,'increment_ms':500,'init_budget_s':90.0,'ply_cap':600,
      'packages':{'chess':'1.11.2','numpy':'2.5.2','numba':'0.67.0','llvmlite':'0.49.0'},
      'official_harness_commit':'91f70e54be07e1bf56311962044a08b822c3af50',
      'source_provenance':source_provenance(ROOT,ROOT/'lab/odin/official-harness-91f70e54'),
      'policy':'User requested112 overnight games. Complete56 fresh paired openings with frozen archives and full competition clocks. No result-based early stopping. Operational faults stop after the current pair and invalidate the promotion gate. No automatic promotion. Evaluate all112 with paired95% bootstrap lower score bound strictly above50%, and zero faults.',
      'suites':{'primary':{'candidate_sha256':digest(args.candidate),'baseline_sha256':BASELINE,'openings_sha256':digest(out/'primary.fen'),'openings':fens,
                          'min_pairs':56,'threshold':.5,'criterion':'paired_ci_lower','lanes':[{'id':lane,'cpu':cpu,'opening_indices':list(range(cpu,56,2))} for lane,cpu in [('a',0),('b',1)]]}}}
validate_plan(plan)
(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'plan_sha256':digest(out/'plan.json'),'candidate_sha256':digest(args.candidate),'games':112}))
