"""Audit completed fit streams, paired matches and native gates without tuning."""
import hashlib,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
streams=[];fits=[]
for pattern in ('train/lane*/results.jsonl','compute-control/results.jsonl','extended/*/results.jsonl','turn-aware/*/results.jsonl','turn-control/*/results.jsonl'):
    for path in sorted(HERE.glob(pattern)):
        rows=[json.loads(s) for s in path.open()];assert rows[-1]['type']=='complete',path
        streams.append(dict(path=path.relative_to(HERE).as_posix(),sha256=sha(path),fits=sum(r['type'] in ('trial','adaptation') for r in rows)))
        for r in rows:
            if r['type'] in ('trial','adaptation'):
                fits.append(dict(stream=path.relative_to(HERE).as_posix(),kind=r['type'],width=r['width'],seed=r['seed'],cap=r.get('pretrain_cap',r['cap']),selected_epoch=r['selected_epoch'],seconds=r['seconds'],mae=r['metrics']['all']['model']['mae'],quiet_mae=r['metrics']['quiet']['model']['mae'],quiet_p90=r['metrics']['quiet']['model']['p90'],guard_mae=r['metrics']['guard']['model']['mae'],endgame_mae=r['metrics']['endgame']['model']['mae'],curve=r['curve']))
matches=[]
for directory in sorted(HERE.glob('match-*')):
    if not directory.is_dir():continue
    files=sorted(directory.glob('lane*.jsonl'))
    expected_lanes=json.loads((directory/'plan.json').read_text()).get('lanes',2)
    if len(files)!=expected_lanes:continue
    games=[];sources={}
    for path in files:
        rr=[json.loads(l) for l in path.open()];assert rr[-1]['type']=='summary',path
        assert rr[-1]['games']==16//expected_lanes;games.extend(r for r in rr if r['type']=='game');sources[path.name]=sha(path)
    pts=np.array([g['candidate_points'] for g in games]);assert len(games)==16
    pairs=[np.mean([g['candidate_points'] for g in games if g['opening_index']==i]) for i in range(8)]
    rng=np.random.default_rng(2026090607);boot=np.mean(rng.choice(pairs,size=(20000,8),replace=True),axis=1)
    matches.append(dict(name=directory.name,wins=int(sum(pts==1)),draws=int(sum(pts==.5)),losses=int(sum(pts==0)),score=float(pts.mean()),paired_bootstrap95=np.quantile(boot,[.025,.975]).tolist(),legal_plies=sum(g['plies'] for g in games),source_sha256=sources,scope='Used-development500ms paired screen; small family sample and no full-clock or independent Elo claim.'))
gates=[]
for path in sorted(HERE.glob('native-*/*-linux.jsonl')):
    rr=[json.loads(l) for l in path.open()];assert rr[-1]['type']=='complete',path
    gates.append(dict(path=path.relative_to(HERE).as_posix(),sha256=sha(path),cold_seconds=rr[0]['cold_seconds'],checks=[r for r in rr if r['type'] in ('checks','policy_checks','isolation')],probes=sum(r['type']=='probe' for r in rr)))
desktop=ROOT.parent/'agent.zip';assert sha(desktop)=='0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4'
report=dict(training_fits=len(fits),streams=streams,fits=fits,matches=matches,native_gates=gates,desktop_sha256=sha(desktop),data={d:json.loads((HERE/d/'manifest.json').read_text())['rows'] for d in ('data','data-r2')},scope='All training/development analyses remain development. Source transports are not submission releases. Original models only; offline teachers/data excluded from runtime source. Sealed evaluation blocks and fresh confirmation families remain unopened.')
(HERE/'results.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(training_fits=len(fits),matches=matches,data=report['data']),indent=2))
