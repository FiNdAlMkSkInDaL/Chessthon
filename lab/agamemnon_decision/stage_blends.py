"""Freeze one-checkpoint blend sweep before its results are known."""
import hashlib, json, shutil, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
DEST=HERE/'native'
SOURCE=DEST/'settled-pair25'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
variants=[('blend15',15),('blend20',20),('blend25a',25),('blend25b',25),('blend30',30),('blend35',35)]
original=(SOURCE/'core_nb.py').read_text()
needle='    score = pesto_nb(bb, st, True) + 100.0 * correction + 0.75 * hand'
assert original.count(needle)==1
source_meta=json.loads((DEST/'settled-pair25.json').read_text())
for name,percent in variants:
    target=DEST/name;target.mkdir(exist_ok=False)
    for p in SOURCE.iterdir():
        if p.suffix in ('.py','.npz'):shutil.copyfile(p,target/p.name)
    if percent!=25:
        line=f'    score = pesto_nb(bb, st, True) + {4.0*percent} * correction + {1-percent/100:.2f} * hand'
        (target/'core_nb.py').write_text(original.replace(needle,line))
    files={p.name:sha(p) for p in target.iterdir() if p.suffix in ('.py','.npz')}
    assert files['value.npz']==source_meta['files']['value.npz']
    assert all(h==source_meta['files'][p] for p,h in files.items() if p!='core_nb.py')
    if percent==25:assert files==source_meta['files']
    meta=dict(source_meta,name=name,mix=percent/100,files=files)
    (DEST/f'{name}.json').write_text(json.dumps(meta,indent=2))
plan=dict(checkpoint_sha256=source_meta['checkpoint_sha256'],mix_percent=[15,20,25,30,35],
    lanes={'0':['blend25a','blend15','blend30'],'1':['blend20','blend35','blend25b']},
    controls='25% repeated on both CPU lanes at opposite sequence ends; source bytes identical to settled-pair25. Weights and all search code except blend expression fixed.',
    gates='Same perft, accumulator/output parity, ABA, cold guard and110 exposed root node/wall diagnostics. No fresh sealed or confirmation roots.',
    selection='Compare each challenger to mean of the two concurrent25% controls. A challenger must reduce wall capped regret, have no greater >200cp count than the worse25% control, and no fixed-node regret regression. Among eligible challengers choose lowest wall regret; ties choose closest to25%. Retain original >=5cp-vs-Tempest nomination gate for a Tempest match. Best challenger plays16 direct paired development games against25%; >=60% permits further confirmation,50-60% inconclusive, below50% rejects. No nested fine sweep or promotion based on this reused diagnostic set.',
    scope='User-requested one-dimensional local tuning. Exploratory selection, not a claim of global optimum or independent Elo.')
(HERE/'blend-plan.json').write_text(json.dumps(plan,indent=2))
with zipfile.ZipFile(HERE/'blend-transport.zip','x',zipfile.ZIP_DEFLATED) as archive:
    for name,_ in variants:
        for p in (DEST/name).iterdir():
            if p.is_file():archive.write(p,p.relative_to(DEST))
        archive.write(DEST/f'{name}.json',f'{name}.json')
print(json.dumps(plan))
