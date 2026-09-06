"""Exact position-only static evaluation cache, disjoint from search TT slots."""
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

CACHE='''# Static evaluation is independent of history, rule50 and cap. It has
# a physically disjoint region in three mutable TT planes, never score bounds.
EVAL_CACHE_SIZE = 1 << 18
EVAL_CACHE_MASK = EVAL_CACHE_SIZE - 1

@njit(cache=False)
def evaluate_cached_nb(bb, st, adjudicate, ttk, tts, ttd):
    key = st[KEY]
    index = TT_SIZE + np.int64(key & np.uint64(EVAL_CACHE_MASK))
    if ttd[index] and ttk[index] == key:
        return np.int32(tts[index])
    score = evaluate_nb(bb,st,adjudicate)
    ttk[index] = key
    tts[index] = np.int16(score)
    ttd[index] = np.uint8(1)
    return score
'''


def main():
    source=ROOT/'odin_positional_cache'
    assert not source.exists()
    source.mkdir()
    for p in (ROOT/'odin_positional').glob('*.py'):shutil.copy2(p,source/p.name)
    core=(source/'core_nb.py').read_text()
    for plane in ('TT_KEY','TT_SCORE','TT_DEPTH'):
        old=plane+' = np.zeros(TT_SIZE,'
        assert core.count(old)==1
        core=core.replace(old,plane+' = np.zeros(TT_SIZE + (1 << 18),')
    insertion=function_text(core,'evaluate_nb')
    core=core.replace(insertion,insertion+'\n\n'+CACHE)
    for name in ('qsearch_nb','negamax_nb'):
        function=function_text(core,name)
        assert function.count('evaluate_nb(bb, st, adjudicate)')==2
        new=function.replace('evaluate_nb(bb, st, adjudicate)','evaluate_cached_nb(bb, st, adjudicate, ttk, tts, ttd)')
        core=core.replace(function,new)
    ast.parse(core)
    (source/'core_nb.py').write_text(core,encoding='utf-8')
    manifest={'source':str(source),'base':'odin_positional','scope':'Exact static value cache, not search result cache',
              'extra_bytes':(1<<18)*(8+2+1),'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')}}
    (HERE/'cache-build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))


if __name__=='__main__':main()
