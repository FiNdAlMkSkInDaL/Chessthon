"""Isolate scaled neural value and upper-tree learned allocation ablations."""
import argparse,hashlib,json,re,shutil,sys,zipfile
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'lab/agamemnon';sys.path.insert(0,str(OLD))
from representations import sha,forward
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--checkpoint',type=Path,required=True);ap.add_argument('--policy',type=Path);ap.add_argument('--name',required=True);ap.add_argument('--leaf',choices=('learned','tempest'),default='learned');a=ap.parse_args()
    dest=HERE/a.name;dest.mkdir(exist_ok=False);checkpoint=a.checkpoint.resolve();z=np.load(checkpoint)
    net=np.concatenate([z['w'],z['bias'][None],z['out'].T]).astype(np.float32);net[:769]=np.rint(net[:769]*4096);assert abs(net[:769]).max()<32767
    variants=('value','order','allocate','uniform') if a.policy else ('value','control')
    for variant in variants:
        src=dest/variant;src.mkdir()
        for p in ((ROOT/'tempest_exact') if variant=='control' else (OLD/'native-delta-r1/delta')).iterdir():
            if p.suffix in ('.py','.npz'):shutil.copyfile(p,src/p.name)
        if variant!='control':np.savez_compressed(src/'value.npz',net=net)
        if variant!='control' and z['out'].shape[1]==4:
            s=(src/'core_nb.py').read_text();begin=s.index('def evaluate_nb(');end=s.index('\n\n\n@njit',begin);body=s[begin:end]
            body=body.replace('        sign = 1.0 if perspective == 0 else -1.0','        head = 769 if perspective == np.int32(st[SIDE]) else 771')
            body=body.replace('correction += sign * act * (phase * net[769,j] + (1-phase)*net[770,j])','correction += act * (phase * net[head,j] + (1-phase)*net[head+1,j])')
            body=body.replace('    if st[SIDE] == 1:\n        correction = -correction\n','')
            assert 'net[head,j]' in body;s=s[:begin]+body+s[end:];(src/'core_nb.py').write_text(s)
        if variant not in ('value','control'):
            pol=np.load(a.policy);packed=np.r_[pol['coef'],pol['calibration']].astype(np.float32);assert len(packed)==130 and packed[128]>0 and 0<packed[129]<1
            np.savez_compressed(src/'policy.npz',policy=packed)
            s=(src/'core_nb.py').read_text();marker='NN_LAST_BB = np.zeros(12, dtype=np.uint64)'
            s=s.replace(marker,'POLICY = np.load(Path(__file__).with_name("policy.npz"))["policy"]\nPOLICY_STATS = np.zeros(4,dtype=np.int64)\n'+marker)
            s,n=re.subn(r'(?m)^(\s*)nn_acc,\n',r'\1nn_acc,\n\1policy,\n\1policy_stats,\n',s);assert n==13,n
            s,n=re.subn(r'\bNN_ACC,','NN_ACC, POLICY, POLICY_STATS,',s);assert n==3,n
            start=s.index('@njit(cache=False)\ndef negamax_nb(');helper=(HERE/'policy_native.txt').read_text()
            if a.leaf=='tempest':helper=helper.replace('evaluate_nb(', 'learned_evaluate_nb(')
            s=s[:start]+helper+'\n'+s[start:]
            start=s.index('def negamax_nb(');end=s.index('def root_search_nb(',start);body=s[start:end]
            needle='    sort_moves(mb, moves_buf, n, ply, hash_move, killers, histy)'
            replacement=needle+'''\n    policy_active = depth >= 5 and not checked and not adjudicate
    priors = np.empty(0,np.float64)
    if policy_active:
        priors = policy_moves_nb(bb,mb,st,moves_buf,n,ply,hash_move,killers,histy,undos[ply],net,nn_last,nn_acc,policy,policy_stats)
'''
            assert body.count(needle)==1;body=body.replace(needle,replacement)
            if variant in ('allocate','uniform'):
                needle='            reduction = quiet_reduction(depth, searched, is_pv, move_history)'
                prob='priors[i]' if variant=='allocate' else '1.0/n'
                replacement=needle+f'''\n            if policy_active:
                reduction = learned_reduction_nb(depth,n,{prob})
                policy_stats[2]+=1
'''
                assert body.count(needle)==1;body=body.replace(needle,replacement)
                body=body.replace('            if reduction and not aborted[0] and score > alpha:', '            if reduction and not aborted[0] and score > alpha:\n                policy_stats[3]+=1')
            s=s[:start]+body+s[end:];(src/'core_nb.py').write_text(s)
        if variant!='control' and a.leaf=='tempest':
            s=(src/'core_nb.py').read_text();s=s.replace('def evaluate_nb(', 'def learned_evaluate_nb(',1)
            start=s.index('@njit(cache=False)\ndef is_repeat(')
            wrapper='''@njit(cache=False)
def evaluate_nb(bb,st,adjudicate,net,nn_last,nn_acc):
    correction=positional_correction_nb(bb,st)
    if st[SIDE]==1:correction=-correction
    return np.int32(pesto_nb(bb,st,True)+correction)

'''
            s=s[:start]+wrapper+s[start:];(src/'core_nb.py').write_text(s)
    # Deployment reference uses quantized original parameters and exact feature inputs.
    data=np.load(OLD/'public-data/transfer-piece.npz');par=[net[:768]/4096,net[768]/4096,net[769:].T]
    if z['out'].shape[1]==4:
        from turn_model import infer_turn,turn_forward
        turns=infer_turn(data['x'],data['counts'],data['phase'],data['base']);pred=data['base']+400*turn_forward(data['x'],data['counts'],data['phase'],turns,*par)
    else:pred=data['base']+400*forward(data['x'],data['counts'],data['phase'],*par,1)
    rows=[json.loads(l) for l in (OLD/'data/rows.jsonl').open()]
    (dest/'eval-cases.json').write_text(json.dumps([dict(fen=r['fen'],expected_white_cp=float(p)) for r,p in zip(rows,pred)]))
    for name in ('perft.json','cases.json'):shutil.copyfile(OLD/'native-delta-r1'/name,dest/name)
    if a.policy:
        cases=json.loads(a.policy.with_name('cases.json').read_text());sys.path.insert(0,str(HERE));from policy import features,predictions
        import chess
        # Match offline quantized evaluator to native features; allow native integer rounding.
        checks=[]
        for r in cases:
            b=chess.Board(r['fen']);boards=[b.copy()]
            for m in r['moves']:bb=b.copy();bb.push_uci(m['uci']);boards.append(bb)
            pp=predictions(boards,par)
            for i,m in enumerate(r['moves']):checks.append(dict(fen=r['fen'],uci=m['uci'],features=features(b,chess.Move.from_uci(m['uci']),pp[0],pp[i+1]).tolist()))
        (dest/'policy-cases.json').write_text(json.dumps(checks))
    shutil.copyfile(HERE/'probe.py',dest/'probe.py')
    files=sorted(p for p in dest.rglob('*') if p.is_file());manifest=dict(checkpoint_sha256=sha(checkpoint),checkpoint=str(checkpoint.relative_to(ROOT)),policy_sha256=sha(a.policy) if a.policy else None,files={p.relative_to(dest).as_posix():sha(p) for p in files},scope='Original trained parameters, Linux research transport only. No engine labels or FEN answer lookup in agent sources. Policy affects upper-tree quiet effort with full-depth fail-high verification; captures/checks/advanced pawns/TT/killers exempt.')
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2))
    with zipfile.ZipFile(HERE/f'{a.name}-transport.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for p in [*files,dest/'manifest.json']:archive.write(p,p.relative_to(dest).as_posix())
    print(json.dumps(dict(variants=variants,checkpoint=manifest['checkpoint'],width=net.shape[1])))
if __name__=='__main__':main()
