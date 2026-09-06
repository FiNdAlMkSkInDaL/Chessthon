"""Freeze training-objective and residual-head candidates for Linux decision tests."""
import argparse,json,shutil,zipfile,hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'lab/agamemnon_scale/frontier/native'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
DEEP='''    hidden=np.empty(16,np.float64)
    for k in range(16):hidden[k]=net[837,k]
    for perspective in range(2):
        offset=773 if perspective==np.int32(st[SIDE]) else 805
        for j in range(32):
            act=min(2.0,max(0.0,nn_acc[perspective,j]/4096.0))
            for k in range(16):hidden[k]+=act*net[offset+j,k]
    for k in range(16):correction+=min(2.0,max(0.0,hidden[k]))*(phase*net[838,k]+(1-phase)*net[839,k])
'''
def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('baseline','models'));a=ap.parse_args();dest=HERE/'native';dest.mkdir(exist_ok=True);names=[]
    if a.mode=='baseline':
        for name in ('tempest','mix25','mix50'):
            src=dest/name;src.mkdir(exist_ok=False)
            for p in (OLD/name).iterdir():
                if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
            shutil.copyfile(OLD/f'{name}.json',dest/f'{name}.json');names.append(name)
        for name in ('roots.json','perft.json','parity.json'):shutil.copyfile(OLD/name,dest/name)
        s=(OLD/'frontier_probe.py').read_text();needle='            hand=c.positional_correction_nb(bb,st)*(1 if b.turn else -1);ref='
        deep="""            if net.shape[0]>773:
                mover=int(st[c.SIDE]);act=np.r_[np.clip(expected[mover]/4096.,0,2),np.clip(expected[1-mover]/4096.,0,2)]
                hidden=np.clip(act@net[773:837,:16]+net[837,:16],0,2)
                corr+=np.dot(hidden,phase*net[838,:16]+(1-phase)*net[839,:16])
"""
        assert needle in s;s=s.replace(needle,deep+needle);(dest/'probe.py').write_text(s)
        plan=dict(primary_seed=260916,replication_seed=260917,objectives=['pair','static','mixed','replay'],deep_objectives=['pair','static'],mixes=[.25,.5],screen_roots=110,screening='Predeclared: >=5cp improvement in equal-wall clipped regret versus repeated Tempest, no extra >200cp errors, and no fixed-node regression. Compare objectives against replay and same-mix baselines. Nominees play paired games; no Elo claim from this screen.',scope='Existing110 exposed development roots, not the sealed320 Lichess roots or fresh competition confirmation openings.')
        (HERE/'screen-plan.json').write_text(json.dumps(plan,indent=2))
    else:
        seen=set();decisions=[]
        for folder in sorted((HERE/'fits-full').iterdir()):
            if not folder.name.endswith('-snapshots') or '260916' not in folder.name:continue
            r=json.loads((folder/'result.json').read_text());checkpoint=folder/'epoch-64.npz';z=np.load(checkpoint);deep='u' in z.files
            net=np.concatenate([z['w'],z['bias'][None],z['out'].T]).astype(np.float32);net[:769]=np.rint(net[:769]*4096);assert abs(net[:769]).max()<32767
            if deep:
                packed=np.zeros((67,32),np.float32);packed[:64,:16]=z['u'];packed[64,:16]=z['b2'];packed[65:67,:16]=z['v'].T;net=np.concatenate([net,packed])
            key=hashlib.sha256(net.tobytes()).hexdigest()
            if key in seen:continue
            seen.add(key)
            for mix in (25,50):
                name=r['kind']+('-deep' if deep else '')+str(mix);src=dest/name;src.mkdir(exist_ok=False)
                for p in (OLD/f'mix{mix}').iterdir():
                    if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
                np.savez_compressed(src/'value.npz',net=net)
                if deep:
                    p=src/'core_nb.py';s=p.read_text();needle='    hand = positional_correction_nb(bb,st)';assert s.count(needle)==1;s=s.replace(needle,DEEP+needle);p.write_text(s)
                meta=dict(name=name,mix=mix/100,features=768,deep=deep,checkpoint=str(checkpoint.relative_to(ROOT)),checkpoint_sha256=sha(checkpoint),files={p.name:sha(p) for p in src.iterdir() if p.suffix in ('.py','.npz')});(dest/f'{name}.json').write_text(json.dumps(meta,indent=2));names.append(name)
            decisions.append(dict(fit=folder.name,action='stage fixed64 checkpoint for fresh-search test',selected_epoch=64,metrics=r['curve'][63]))
        (HERE/'model-selection.json').write_text(json.dumps(decisions,indent=2))
    (HERE/f'{a.mode}-variants.json').write_text(json.dumps(names))
    with zipfile.ZipFile(HERE/f'{a.mode}-transport.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            for p in (dest/name).iterdir():
                if p.is_file():archive.write(p,p.relative_to(dest))
            archive.write(dest/f'{name}.json',f'{name}.json')
        if a.mode=='baseline':
            for name in ('roots.json','perft.json','parity.json','probe.py'):archive.write(dest/name,name)
    print(json.dumps(names))
if __name__=='__main__':main()
