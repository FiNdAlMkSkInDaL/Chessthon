"""Freeze additional predeclared integration ablations without changing prior runs."""
import json,shutil,zipfile
from train import HERE,sha
from pathlib import Path
def main():
    dest=HERE/'frontier/native'
    for name in ('bounded50','pruning50'):
        src=dest/name;src.mkdir(exist_ok=False)
        for p in (dest/'mix50').iterdir():
            if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
        s=(src/'core_nb.py').read_text()
        if name=='bounded50':
            old='    score = pesto_nb(bb, st, True) + 200.0 * correction + 0.5 * hand'
            new='    delta = max(-200.0,min(200.0,400.0*correction-hand))\n    score = pesto_nb(bb, st, True) + hand + 0.5*delta'
            assert old in s;s=s.replace(old,new)
        else:
            old='        static_eval = evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc)'
            new='        hand = positional_correction_nb(bb,st)\n        if st[SIDE]==1:hand=-hand\n        static_eval = np.int32(pesto_nb(bb,st,True)+hand)'
            assert s.count(old)==1;s=s.replace(old,new)
        (src/'core_nb.py').write_text(s);meta=json.loads((dest/'mix50.json').read_text());meta.update(name=name,files={p.name:sha(p) for p in src.iterdir() if p.suffix in ('.py','.npz')});(dest/f'{name}.json').write_text(json.dumps(meta,indent=2))
    # Probe reference explicitly accounts for bounded correction; all other gates unchanged.
    p=dest/'frontier_probe.py';s=p.read_text();old='            maximum=max(maximum,abs(value-ref));assert abs(value-ref)<1.01,(fen,value,ref);checks+=1'
    new="            if a.variant=='bounded50':ref=c.pesto_nb(bb,st,True)+hand+.5*np.clip(400*corr-hand,-200,200)\n"+old
    assert old in s;s=s.replace(old,new);(dest/'frontier_probe_ext.py').write_text(s)
    plan=dict(candidates=['bounded50','pruning50'],screen='Same frozen110 development roots and original5cp equal-wall gate. bounded50 caps disagreement correction at100cp; pruning50 keeps Tempest static score for RFP/NMP/futility while hybrid remains at leaves.',scope='Architectural integration ablations, not a new holdout or a changed acceptance threshold.')
    (HERE/'frontier/extension-plan.json').write_text(json.dumps(plan,indent=2))
    with zipfile.ZipFile(HERE/'frontier/extension.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name in plan['candidates']:
            for p in (dest/name).iterdir():
                if p.is_file():z.write(p,p.relative_to(dest))
            z.write(dest/f'{name}.json',f'{name}.json')
        z.write(dest/'frontier_probe_ext.py','frontier_probe_ext.py')
if __name__=='__main__':main()
