"""Freeze isolated frontier sources, including exact king-context lazy updates."""
import json,shutil,zipfile
from pathlib import Path
import numpy as np
from train import HERE,ROOT,sha

BODY='''def evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc):
    feature_count = net.shape[0]-5
    phase = min(24, np.int64(st[PHASE_ACC])) / 24.0
    for perspective in range(2):
        flip=0 if perspective==0 else 56
        king_piece=5+6*perspective
        refresh = nn_last[king_piece] != bb[king_piece] and feature_count>768
        king=lsb(bb[king_piece])^flip
        if refresh:
            for j in range(net.shape[1]):nn_acc[perspective,j]=np.int32(net[feature_count,j])
        for piece in range(12):
            removed = np.uint64(0) if refresh else nn_last[piece] & ~bb[piece]
            added = bb[piece] if refresh else bb[piece] & ~nn_last[piece]
            pt=piece if perspective==0 else (piece+6)%12
            for change in range(2):
                bits=removed if change==0 else added
                sign=-1 if change==0 else 1
                while bits:
                    sq=lsb(bits)^flip;bits &= bits-np.uint64(1)
                    idx=pt*64+sq
                    rel=768+pt*225+(sq//8-king//8+7)*15+sq%8-king%8+7
                    for j in range(net.shape[1]):
                        nn_acc[perspective,j]+=sign*np.int32(net[idx,j])
                        if feature_count>768:nn_acc[perspective,j]+=sign*np.int32(net[rel,j])
    for piece in range(12):nn_last[piece]=bb[piece]
    correction=0.
    for perspective in range(2):
        head=feature_count+1 if perspective==np.int32(st[SIDE]) else feature_count+3
        for j in range(net.shape[1]):
            act=min(2.,max(0.,nn_acc[perspective,j]/4096.))
            correction+=act*(phase*net[head,j]+(1-phase)*net[head+1,j])
    base=pesto_nb(bb,st,True)
    neural=400.*correction
    handcrafted=positional_correction_nb(bb,st)
    if st[SIDE]==1:handcrafted=-handcrafted
    score=base+MIX*neural+(1.-MIX)*handcrafted
    return np.int32(max(-30000.,min(30000.,score)))
'''

def main():
    dest=HERE/'frontier/native';dest.mkdir(parents=True,exist_ok=False)
    rank=[]
    for seed in (260910,260911,260912):
        p=HERE/f'frontier/rank-{seed}';r=json.loads((p/'result.json').read_text());e=r['selected_epoch'];score=r['curve'][e-1]['regret']['mean'] if e else float('inf');rank.append((score,p/'adapted.npz'))
    rankpath=min(rank)[1]
    turn=HERE/'turn-aware/s260909/adapted.npz';relative=HERE/'frontier/relative-260909/adapted.npz'
    cases=[('turn',turn,1.),('mix25',turn,.25),('mix50',turn,.5),('rank50',rankpath,.5),('rank',rankpath,1.),('relative50',relative,.5)]
    for name,checkpoint,mix in cases:
        src=dest/name;src.mkdir();original=HERE/'native-turn-r1/value'
        for p in original.iterdir():
            if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
        z=np.load(checkpoint);n=len(z['w']);net=np.concatenate([z['w'],z['bias'][None],z['out'].T]).astype(np.float32);net[:n+1]=np.rint(net[:n+1]*4096);assert abs(net[:n+1]).max()<32767
        np.savez_compressed(src/'value.npz',net=net)
        s=(src/'core_nb.py').read_text();s=s.replace('NN_ACC = np.tile(NET[768].astype(np.int32), (2,1))',f'NN_ACC = np.tile(NET[{n}].astype(np.int32), (2,1))')
        begin=s.index('def evaluate_nb(');end=s.index('\n\n\n@njit',begin)
        if n>768:s=s[:begin]+BODY.replace('MIX',str(mix)).rstrip()+s[end:]
        elif mix!=1:
            body=s[begin:end];old='    score = pesto_nb(bb, st, True) + 400.0 * correction'
            new=f'    hand = positional_correction_nb(bb,st)\n    if st[SIDE]==1:hand=-hand\n    score = pesto_nb(bb, st, True) + {400*mix} * correction + {1-mix} * hand';assert old in body;s=s[:begin]+body.replace(old,new)+s[end:]
        (src/'core_nb.py').write_text(s)
        (dest/f'{name}.json').write_text(json.dumps(dict(name=name,mix=mix,features=n,checkpoint=str(checkpoint.relative_to(ROOT)),checkpoint_sha256=sha(checkpoint),files={p.name:sha(p) for p in src.iterdir() if p.suffix in ('.py','.npz')}),indent=2))
    src=dest/'tempest';src.mkdir()
    for p in (ROOT/'tempest_exact').iterdir():
        if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
    (dest/'tempest.json').write_text(json.dumps(dict(name='tempest',mix=0,features=0,files={p.name:sha(p) for p in src.iterdir() if p.suffix in ('.py','.npz')}),indent=2))
    groups=json.loads((HERE/'frontier/decisions/groups.json').read_text());groups=[r for r in groups if r['split']==1];assert len(groups)==110
    # Whole reused root groups; no new sealed test states.
    (dest/'roots.json').write_text(json.dumps(groups))
    shutil.copyfile(HERE/'native-turn-r1/perft.json',dest/'perft.json')
    shutil.copyfile(HERE/'frontier_probe.py',dest/'frontier_probe.py')
    rows=[json.loads(l) for l in (HERE.parent/'agamemnon/data/rows.jsonl').read_text().splitlines()]
    (dest/'parity.json').write_text(json.dumps([r['fen'] for r in rows]))
    plan=dict(candidates=['tempest']+[r[0] for r in cases],roots=110,node_budget=200000,wall_ms=300,scope='Reused development full-alternative teacher regret; finite16k teacher, no independent Elo or release inference. Cold import, perft, parity, ABA required before root screens. Then compare finalists in paired games.',screening='Nominate only if equal-wall clipped regret improves by at least5cp, >200cp mistake count does not increase, and fixed-node regret does not regress. These development conditions do not prove strength.')
    (dest/'plan.json').write_text(json.dumps(plan,indent=2))
    with zipfile.ZipFile(HERE/'frontier/transport.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in dest.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(dest))
    print(json.dumps(plan))

if __name__=='__main__':main()
