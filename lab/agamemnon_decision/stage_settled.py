"""Stage the primary replicated settled-leaf preference checkpoint."""
import hashlib,json,shutil,zipfile
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];dest=HERE/'native';old=ROOT/'lab/agamemnon_scale/frontier/native'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checkpoint=HERE/'fits-settled/pair-260916-soft-snapshots/model.npz';z=np.load(checkpoint);net=np.concatenate([z['w'],z['bias'][None],z['out'].T]).astype(np.float32);net[:769]=np.rint(net[:769]*4096)
plan=dict(checkpoint=str(checkpoint.relative_to(ROOT)),primary_seed=260916,selection='Primary pair fit, selected on307 reused-development groups by the original checkpoint rule. Replication seed260917 also improves the conditional surrogate; fresh-search and games still decide.',variants=['settled-pair25','settled-pair50'])
for mix in (25,50):
    name=f'settled-pair{mix}';src=dest/name;src.mkdir(exist_ok=False)
    for p in (old/f'mix{mix}').iterdir():
        if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
    np.savez_compressed(src/'value.npz',net=net);meta=dict(name=name,mix=mix/100,features=768,checkpoint=plan['checkpoint'],checkpoint_sha256=sha(checkpoint),files={p.name:sha(p) for p in src.iterdir() if p.suffix in ('.py','.npz')});(dest/f'{name}.json').write_text(json.dumps(meta,indent=2))
(HERE/'settled-screen-plan.json').write_text(json.dumps(plan,indent=2))
with zipfile.ZipFile(HERE/'settled-transport.zip','x',zipfile.ZIP_DEFLATED) as archive:
    for name in plan['variants']:
        for p in (dest/name).iterdir():
            if p.is_file():archive.write(p,p.relative_to(dest))
        archive.write(dest/f'{name}.json',f'{name}.json')
print(json.dumps(plan))
