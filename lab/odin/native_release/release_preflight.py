"""Validate final packaging/native evidence without claiming pending match gates."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.odin.promotion.promote import inspect_archive,validate_contract,validate_gate,validate_desktop
from lab.odin.release.plan import source_provenance

stage=ROOT/'lab/odin/native_release/odin-release-r10'
manifest=inspect_archive((stage/'candidate-linux-x86.zip').read_bytes(),ROOT/'odin_submission')
plan=json.loads((stage/'final112/plan.json').read_text(encoding='utf-8'))
validate_contract(plan,manifest['sha256'])
assert source_provenance(ROOT,ROOT/'lab/odin/official-harness-91f70e54')==plan['source_provenance']
gate=json.loads((stage/'native-gate.json').read_text(encoding='utf-8'))
native=validate_gate(gate,manifest,plan)
backups=validate_desktop(ROOT.parent,manifest['sha256'])
result={'scope':'Exact source/archive/native evidence only. Complete primary and guard match gates remain mandatory.',
        'verdict':'PASS','native':native,'desktop':backups,'entries':manifest['entry_count'],'bytes':manifest['zip_bytes']}
(stage/'release-preflight.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
