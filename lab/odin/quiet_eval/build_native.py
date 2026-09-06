"""Transport source builder; Linux cold/resource and playing gates still required."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from lab.odin.storm_plus.build_storm_plus import function_text


def main():
    source=ROOT/'odin_positional'
    assert not source.exists()
    source.mkdir()
    for file in (ROOT/'odin_storm_plus').glob('*.py'):
        shutil.copy2(file,source/file.name)
    fit=json.loads((HERE/'expanded-result.json').read_text())
    core=(source/'core_nb.py').read_text(encoding='utf-8')
    implementation=(HERE/'native_features.txt').read_text().replace('__MG__',repr(fit['mg'])).replace('__EG__',repr(fit['eg']))
    core=core.replace(function_text(core,'evaluate_nb'),implementation)
    ast.parse(core)
    (source/'core_nb.py').write_text(core,encoding='utf-8')
    # Match the fallback evaluator without any training code dependency.
    # It calls the same pure feature function, not the native dispatcher.
    fallback=(source/'eval_nb.py').read_text(encoding='utf-8')
    fallback += '\n\n# Positional correction is native-only in this experimental candidate.\n# A fallback remains legal vanilla PeSTO; release requires native readiness.\n'
    (source/'eval_nb.py').write_text(fallback,encoding='utf-8')
    manifest={'source':str(source),'fit_sha256':hashlib.sha256((HERE/'expanded-result.json').read_bytes()).hexdigest(),
              'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')},
              'status':'EXPERIMENTAL; no claim of strength improvement'}
    (HERE/'native-build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))


if __name__=='__main__':main()
