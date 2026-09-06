"""Prepare reviewable Odin source; does not promote or decide strength gates."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.odin.storm_plus.build_storm_plus import function_text


def main():
    source=ROOT/'odin_submission'
    assert not source.exists(),'Refusing to replace canonical source'
    source.mkdir()
    base=ROOT/'odin_positional'
    for file in base.glob('*.py'):shutil.copy2(file,source/file.name)
    changes=[]
    for filename,function,condition in [
        ('core_nb.py','fifty_claim_nb','np.int32(st[FIFTY]) < 99 or nlegal <= 0'),
        ('search_nb.py','_fifty_claim_from_legal','pos.fifty < 99 or not legal')]:
        original=(source/filename).read_text(encoding='utf-8')
        original_fn=function_text(original,function)
        tree=ast.parse(original_fn)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef))
        body_index=1 if isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant) and isinstance(fn.body[0].value.value,str) else 0
        lines=original_fn.splitlines(keepends=True)
        # Insert before first executable statement, retaining readable source.
        insert_at=fn.body[body_index].lineno-1
        lines.insert(insert_at,f'    if {condition}:\n        return False\n')
        new_fn=''.join(lines)
        verified=ast.parse(new_fn).body[0]
        del verified.body[body_index]
        assert ast.dump(verified)==ast.dump(fn),'Only the precondition repair may differ'
        updated=original.replace(original_fn,new_fn)
        (source/filename).write_text(updated,encoding='utf-8')
        changes.append({'file':filename,'function':function,'guard':condition,
                        'behavior':'Adds false outside the old helper caller domain; existing search callers already enforce these conditions.'})
    agent=(source/'agent.py').read_text(encoding='utf-8')
    agent=agent.replace('# Storm v4. Own selective search, exact incremental PeSTO and evidence-driven\n# time control on the proven v3 move representation and legal-move foundation.',
        '# Odin v5. Storm-derived selective search with original offline-fitted\n# positional evaluation, legal SEE/EP and current 600-ply referee handling.\n# The historical S4 stderr tag is retained for telemetry parser compatibility.')
    (source/'agent.py').write_text(agent,encoding='utf-8')
    eval_text=(source/'eval_nb.py').read_text(encoding='utf-8')
    olddoc=ast.parse(eval_text).body[0]
    lines=eval_text.splitlines(keepends=True)
    lines[olddoc.lineno-1:olddoc.end_lineno]=['"""PeSTO base tables and legal Python fallback evaluation.\n\nOdin adds its original fitted positional correction in the native hot path.\nThe live referee uses a 600-ply draw, never kingless material adjudication.\n"""\n']
    (source/'eval_nb.py').write_text(''.join(lines),encoding='utf-8')
    for p in source.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
    manifest={'source':'odin_submission','base':'odin_positional','changes':changes,
              'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')},
              'status':'PREPARED ONLY. Development selection and exact final Linux80+32 gates still required.'}
    (ROOT/'lab/odin/native_release/positional-release-source.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))


if __name__=='__main__':main()
