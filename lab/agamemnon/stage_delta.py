"""Original exact lazy-delta neural evaluator and quantized refresh control.

The cache describes the LAST EVALUATED board, not a presumed search parent.
Bitboard set differences make arbitrary jumps, null moves and skipped evaluations
safe. Integer feature sums cannot accumulate floating-point update drift.
"""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
import numpy as np
from representations import forward,HERE,sha

EVAL='''def evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc):
    phase = min(24, np.int64(st[PHASE_ACC])) / 24.0
    for piece in range(12):
        removed = nn_last[piece] & ~bb[piece]
        added = bb[piece] & ~nn_last[piece]
        for change in range(2):
            bits = removed if change == 0 else added
            sign = -1 if change == 0 else 1
            while bits:
                sq = lsb(bits)
                bits &= bits - np.uint64(1)
                white_idx = piece * 64 + sq
                black_idx = ((piece + 6) % 12) * 64 + (sq ^ 56)
                for j in range(net.shape[1]):
                    nn_acc[0,j] += sign * np.int32(net[white_idx,j])
                    nn_acc[1,j] += sign * np.int32(net[black_idx,j])
        nn_last[piece] = bb[piece]
    correction = 0.0
    for perspective in range(2):
        sign = 1.0 if perspective == 0 else -1.0
        for j in range(net.shape[1]):
            act = min(2.0, max(0.0, nn_acc[perspective,j] / 4096.0))
            correction += sign * act * (phase * net[769,j] + (1-phase)*net[770,j])
    if st[SIDE] == 1:
        correction = -correction
    score = pesto_nb(bb, st, True) + 400.0 * correction
    return np.int32(max(-30000.0, min(30000.0, score)))'''

def main():
    dest=HERE/'native-delta-r1';dest.mkdir(exist_ok=False);original=HERE/'native-prototype-r2'
    packed=np.load(original/'acc32/value.npz')['net'];q=packed.copy();q[:769]=np.rint(q[:769]*4096)
    assert np.max(np.abs(q[:769]))<32767
    for variant in ('quant_refresh','delta'):
        source=dest/variant;source.mkdir()
        for p in (original/'acc32').iterdir():
            if p.suffix in ('.py','.npz'):shutil.copyfile(p,source/p.name)
        np.savez_compressed(source/'value.npz',net=q)
        core=source/'core_nb.py';s=core.read_text()
        if variant=='quant_refresh':s=s.replace('act = min(2.0, max(0.0, accum[j]))','act = min(2.0, max(0.0, accum[j] / 4096.0))')
        else:
            marker='NET = np.load(Path(__file__).with_name("value.npz"))["net"]\n'
            assert marker in s;s=s.replace(marker,marker+'NN_LAST_BB = np.zeros(12, dtype=np.uint64)\nNN_ACC = np.tile(NET[768].astype(np.int32), (2,1))\n')
            s,n=re.subn(r'(?m)^(\s*)net,\n',r'\1net,\n\1nn_last,\n\1nn_acc,\n',s);assert n==13,n
            s,n=re.subn(r'\bNET,', 'NET, NN_LAST_BB, NN_ACC,',s);assert n==3,n
            start=s.index('def evaluate_nb(');end=s.index('\n\n\n@njit',start);s=s[:start]+EVAL+s[end:]
            assert s.count('evaluate_nb(bb, st, adjudicate, net)')==4
            s=s.replace('evaluate_nb(bb, st, adjudicate, net)','evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc)')
        core.write_text(s)
    z=np.load(HERE/'public-data/transfer-piece.npz');quant=[q[:768]/4096,q[768]/4096,q[769:771].T]
    predictions=z['base']+400*forward(z['x'],z['counts'],z['phase'],*quant,1)
    prior=np.load(HERE/'transfer-screen/lane0/public-acc32-public-260906.npz')['pred'];error=abs(predictions-prior)
    rows=[json.loads(l) for l in (HERE/'data/rows.jsonl').open()]
    (dest/'eval-cases.json').write_text(json.dumps([dict(fen=r['fen'],expected_white_cp=float(p)) for r,p in zip(rows,predictions)]))
    for name in ('perft.json','cases.json'):shutil.copyfile(original/name,dest/name)
    shutil.copyfile(HERE/'delta_probe.py',dest/'delta_probe.py')
    files=sorted(p for p in dest.rglob('*') if p.is_file())
    manifest=dict(stage_sha256=sha(__file__),source_manifest_sha256=sha(original/'manifest.json'),quantization=dict(scale=4096,mean_abs_cp=float(error.mean()),max_abs_cp=float(error.max()),positions=len(error),max_integer_feature=float(np.max(abs(q[:769])))),files={p.relative_to(dest).as_posix():sha(p) for p in files},scope='Original integer feature delta cache; learned output float32. Identical quantized refresh model is control. Research source transport only.')
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2))
    with zipfile.ZipFile(HERE/'delta-transport-r1.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for p in [*files,dest/'manifest.json']:archive.write(p,p.relative_to(dest).as_posix())
    print(json.dumps(manifest['quantization']))
if __name__=='__main__':main()
