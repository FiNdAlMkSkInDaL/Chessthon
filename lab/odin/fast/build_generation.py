"""Original, bounded search/evaluation generation. Reuses no final holdout."""
import json,re,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
configs=[
 ('guards',{'guards':True}),
 ('lmr_cautious',{'replace':{'0.75 + np.log(_depth) * np.log(_move_number) / 2.25':'0.50 + np.log(_depth) * np.log(_move_number) / 2.75'}}),
 ('lmr_fast',{'replace':{'0.75 + np.log(_depth) * np.log(_move_number) / 2.25':'0.85 + np.log(_depth) * np.log(_move_number) / 1.95'}}),
 ('history_lmr',{'replace':{'    if history_score > 4000:\n        reduction -= 1\n    elif history_score < -4000:\n        reduction += 1':'    reduction -= max(-2, min(2, history_score // 5000))'}}),
 ('tactical',{'constants':{'RFP_MAX_D':4,'RFP_MARGIN':110,'SEE_PRUNE_MAX_D':4,'SEE_PRUNE_MARGIN':110}}),
 ('pawn_futility',{'futility':True}),
 ('null_cautious',{'replace':{'r = 2 + depth // 5 + min(2, (static_eval - beta) // 200)':'r = 2 + depth // 6 + min(1, (static_eval - beta) // 300)'}}),
 ('iir_late',{'constants':{'IIR_MIN_D':6}}),
 ('iir_off',{'constants':{'IIR_MIN_D':65}}),
 ('positional_gain',{'replace':{'return max(-400,min(400,score))':'return max(-500,min(500,score * 5 // 4))'}}),
 ('king_safety',{'mg':{9:12,10:-80,16:4}}),
 ('passers',{'futility':True,'eg':{3:12,5:-8,6:8,17:7}}),
 ('see_order',{'see_order':True}),
 ('mobility',{'mg':{12:3,13:6,14:2,15:1},'eg':{12:4,13:7,14:5}}),
]
population=ROOT/'odin_generation';population.mkdir(exist_ok=False);manifest=[]
base=(ROOT/'odin_submission/core_nb.py').read_text(encoding='utf-8')
for idx,(name,config) in enumerate(configs):
    source=population/name;source.mkdir()
    for p in (ROOT/'odin_submission').glob('*.py'):shutil.copy2(p,source/p.name)
    s=(ROOT/'odin_v6_guards/core_nb.py').read_text(encoding='utf-8') if config.get('guards') else base
    if config.get('futility'):
        old='        move_history = histy[mover, m_to(move)] if quiet else 0\n'
        s=s.replace(old,old+'        critical_pawn = mover % 6 == 0 and ((mover == 0 and m_to(move) >= 40) or (mover == 6 and m_to(move) < 24))\n')
        s=s.replace('            and depth <= FF_MAX_D\n','            and searched > 0\n            and not critical_pawn\n            and depth <= FF_MAX_D\n')
    for key,val in config.get('constants',{}).items():s,n=re.subn(r'^'+key+r' = \d+$',key+' = '+str(val),s,flags=re.M);assert n==1
    for old,new in config.get('replace',{}).items():assert s.count(old)==1;s=s.replace(old,new)
    for phase in ('mg','eg'):
        if phase not in config:continue
        pat=r'FEATURE_'+phase.upper()+r' = np.array\((\[[^\n]+?\]), dtype=np.int32\)'
        m=re.search(pat,s);vals=json.loads(m.group(1))
        for k,v in config[phase].items():vals[k]=v
        s=s[:m.start(1)]+json.dumps(vals)+s[m.end(1):]
    if config.get('see_order'):
        old='def sort_moves(mb, moves, n, ply, hash_move, killers, histy):';assert s.count(old)==1
        s=s.replace(old,'def sort_moves(bb, mb, st, moves, n, ply, hash_move, killers, histy):')
        s=s.replace('sort_moves(mb,','sort_moves(bb, mb, st,')
        old='        a, b = order_key(mb, moves[i], ply, hash_move, killers, histy)\n';assert s.count(old)==1
        s=s.replace(old,old+'        if a == 1 and m_cap(moves[i]) and not m_promo(moves[i]) and see_nb(bb, mb, st, moves[i]) < 0:\n            a = 5  # Search losing captures after useful quiet moves.\n')
    (source/'core_nb.py').write_text(s,encoding='utf-8',newline='\n')
    p=source/'agent.py';p.write_text(p.read_text(encoding='utf-8').replace('Odin v5.','Odin generation '+name+'.'),encoding='utf-8',newline='\n')
    manifest.append({'name':name,'source':source.relative_to(ROOT).as_posix(),'config':config,
                     'lane':('linux-a' if idx%2==0 else 'linux-b') if idx<12 else ('windows-a' if idx==12 else 'windows-b'),
                     'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob('*.py'))}})
policy={'generation':manifest,'baseline':'odin_submission','stage1':{'pairs':9,'nodes':20000,'complete_all':True},
        'stage2':{'pairs':24,'nodes':100000,'candidates':'Top3 by stage1 paired points. Ties prefer fewer altered parameters; no selection based on unfinished games. Stage2 uses fresh families; include a combined candidate only after independent component gains and declare it before stage2 starts.'},
        'selection':'Exploratory population ranking only. Rank finalists by complete stage2 points vs released Odin. Winner must score above50% with zero faults and pass exact-source native gate before112 untouched full-clock games. No guarantee of a large improvement; no parameter or candidate changes after overnight freeze.'}
(HERE/'generation-policy.json').write_text(json.dumps(policy,indent=2)+'\n');print(json.dumps({'candidates':len(manifest),'lanes':{r['name']:r['lane'] for r in manifest}}))
