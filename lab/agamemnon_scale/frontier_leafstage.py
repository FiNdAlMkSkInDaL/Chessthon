"""Nominate one mined-leaf checkpoint on reused development, then isolate mixing."""
import json,shutil,zipfile
import numpy as np
from train import HERE,ROOT,sha
def main():
    trials=[]
    for seed in (260913,260914):
        p=HERE/f'frontier/leaf-{seed}';r=json.loads((p/'result.json').read_text())
        if r['after_old_mae']<240:trials.append((r['result']['metrics']['all']['model']['mae'],p/'adapted.npz'))
    assert trials,'No mined-leaf fit retained old-state error guard'
    checkpoint=min(trials)[1];z=np.load(checkpoint);net=np.concatenate([z['w'],z['bias'][None],z['out'].T]).astype(np.float32);net[:769]=np.rint(net[:769]*4096);assert abs(net[:769]).max()<32767
    dest=HERE/'frontier/native';names=[]
    for name,source,mix in [('leaf25','mix25',.25),('leaf50','mix50',.5),('leaf','turn',1.)]:
        names.append(name);src=dest/name;src.mkdir(exist_ok=False)
        for p in (dest/source).iterdir():
            if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
        np.savez_compressed(src/'value.npz',net=net)
        meta=json.loads((dest/f'{source}.json').read_text());meta.update(name=name,checkpoint=str(checkpoint.relative_to(ROOT)),checkpoint_sha256=sha(checkpoint),files={p.name:sha(p) for p in src.iterdir() if p.suffix in ('.py','.npz')});(dest/f'{name}.json').write_text(json.dumps(meta,indent=2))
    plan=dict(candidates=names,checkpoint=str(checkpoint.relative_to(ROOT)),selection='Lowest mined-state development MAE with prior-state MAE<240cp; mixing factors fixed before root tests. Same110 roots, node/time allowances and5cp nomination gate. No new test-set claim.')
    (HERE/'frontier/leaf-plan.json').write_text(json.dumps(plan,indent=2))
    with zipfile.ZipFile(HERE/'frontier/leaf.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            for p in (dest/name).iterdir():
                if p.is_file():archive.write(p,p.relative_to(dest))
            archive.write(dest/f'{name}.json',f'{name}.json')
    print(json.dumps(plan))
if __name__=='__main__':main()
