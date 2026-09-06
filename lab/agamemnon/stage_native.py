"""Isolate a refresh-evaluation bridge for equal-wall search feasibility.
This is not the final incremental architecture, and is never a release archive.
"""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def main():
    dest=HERE/'native-prototype-r2';dest.mkdir(exist_ok=False)
    for name in ('control','acc32'):
        source=dest/name;source.mkdir()
        for p in (ROOT/'tempest_exact').iterdir():
            if p.suffix in ('.py','.npz'):shutil.copyfile(p,source/p.name)
    ck=HERE/'transfer-screen/lane0/public-acc32-public-260906.npz';z=np.load(ck)
    weights=np.concatenate([z['w'],z['bias'][None],z['out'].T],axis=0).astype(np.float32)
    np.savez_compressed(dest/'acc32/value.npz',net=weights)
    core=dest/'acc32/core_nb.py';s=core.read_text();s=s.replace('import time\n','import time\nfrom pathlib import Path\n',1)
    # Load after NumPy import, then pass parameters explicitly through recursion.
    s=s.replace('import numpy as np\n','import numpy as np\nNET = np.load(Path(__file__).with_name("value.npz"))["net"]\n',1)
    s,n=re.subn(r'(?m)^(\s*)histy,\n',r'\1histy,\n\1net,\n',s);assert n==13,n
    s,n=re.subn(r'\bHISTORY,', 'HISTORY, NET,',s);assert n==3,n
    old='''def evaluate_nb(bb, st, adjudicate):
    correction = positional_correction_nb(bb,st)
    if st[SIDE] == 1:
        correction = -correction
    return np.int32(pesto_nb(bb,st,True)+correction)'''
    new='''def evaluate_nb(bb, st, adjudicate, net):
    phase = min(24, np.int64(st[PHASE_ACC])) / 24.0
    correction = 0.0
    for perspective in range(2):
        accum = net[768].copy()
        for piece in range(12):
            bits = bb[piece]
            rel = piece if perspective == 0 else (piece + 6) % 12
            while bits:
                sq = lsb(bits)
                bits &= bits - np.uint64(1)
                idx = rel * 64 + (sq if perspective == 0 else sq ^ 56)
                for j in range(net.shape[1]):
                    accum[j] += net[idx, j]
        sign = 1.0 if perspective == 0 else -1.0
        for j in range(net.shape[1]):
            act = min(2.0, max(0.0, accum[j]))
            correction += sign * act * (phase * net[769,j] + (1-phase)*net[770,j])
    if st[SIDE] == 1:
        correction = -correction
    score = pesto_nb(bb, st, True) + 400.0 * correction
    return np.int32(max(-30000.0, min(30000.0, score)))'''
    assert old in s;s=s.replace(old,new)
    assert s.count('evaluate_nb(bb, st, adjudicate)')==4
    s=s.replace('evaluate_nb(bb, st, adjudicate)','evaluate_nb(bb, st, adjudicate, net)')
    core.write_text(s)
    cases=json.loads((ROOT/'lab/tempest_edges/gate-cases.json').read_text())
    # Predeclared used diagnostics: first six available cases, no label selection.
    (dest/'cases.json').write_text(json.dumps(cases[:6],indent=2))
    states=[json.loads(l) for l in (HERE/'data/rows.jsonl').open()][:300]
    pred=z['pred'][:300]
    (dest/'eval-cases.json').write_text(json.dumps([dict(fen=r['fen'],expected_white_cp=float(v)) for r,v in zip(states,pred)]))
    shutil.copyfile(HERE/'native_probe.py',dest/'native_probe.py')
    from sys import path
    path.insert(0,str(ROOT));from lab.perft import POSITIONS
    (dest/'perft.json').write_text(json.dumps(POSITIONS))
    files=sorted(p for p in dest.rglob('*') if p.is_file())
    manifest=dict(kind='Source transport only, not a Linux release/archive recommendation',source_release='Tempest r1',stage_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),checkpoint_sha256=hashlib.sha256(ck.read_bytes()).hexdigest(),files={p.relative_to(dest).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},scope='Neural evaluation refresh bridge. No incremental state in search yet; parameters passed explicitly avoid baking learned arrays into JIT code.')
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2))
    with zipfile.ZipFile(HERE/'native-transport-r2.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for p in [*files,dest/'manifest.json']:archive.write(p,p.relative_to(dest).as_posix())
    print(len(files),len(s))
if __name__=='__main__':main()
