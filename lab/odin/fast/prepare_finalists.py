"""Predeclare top3 plus one compatible positive-component combination."""
import json,re,shutil,hashlib,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
report=json.loads((HERE/'generation-report.json').read_text());assert report['complete']
policy=json.loads((HERE/'generation-policy.json').read_text());jobs={r['name']:r for r in policy['generation']}
results={r['name']:r for r in report['candidates']};ranking=report['ranking'];chosen=[jobs[n].copy() for n in ranking[:3]]
def keys(config):
    out=set()
    for kind,val in config.items():
        if kind in ('constants','replace','mg','eg'):out.update((kind,str(k)) for k in val)
        else:out.add((kind,''))
    if config.get('guards'):out.update({('futility',''),('null','')})
    return out
first=jobs[ranking[0]];second=next((jobs[n] for n in ranking[1:] if results[n]['score']>.5 and not (keys(first['config'])&keys(jobs[n]['config'])) and not jobs[n]['config'].get('guards')),None)
if second and results[first['name']]['score']>.5:
    name='combined_'+first['name']+'_'+second['name'];source=ROOT/'odin_generation'/name;source.mkdir(exist_ok=False)
    for p in (ROOT/first['source']).glob('*.py'):shutil.copy2(p,source/p.name)
    p=source/'core_nb.py';s=p.read_text(encoding='utf-8');config=second['config']
    if config.get('futility'):
        old='        move_history = histy[mover, m_to(move)] if quiet else 0\n';assert s.count(old)==1
        s=s.replace(old,old+'        critical_pawn = mover % 6 == 0 and ((mover == 0 and m_to(move) >= 40) or (mover == 6 and m_to(move) < 24))\n')
        s=s.replace('            and depth <= FF_MAX_D\n','            and searched > 0\n            and not critical_pawn\n            and depth <= FF_MAX_D\n')
    for key,val in config.get('constants',{}).items():s,n=re.subn(r'^'+key+r' = \d+$',key+' = '+str(val),s,flags=re.M);assert n==1
    for old,new in config.get('replace',{}).items():assert s.count(old)==1;s=s.replace(old,new)
    for phase in ('mg','eg'):
        if phase not in config:continue
        pat=r'FEATURE_'+phase.upper()+r' = np.array\((\[[^\n]+?\]), dtype=np.int32\)';m=re.search(pat,s);vals=json.loads(m.group(1))
        for k,v in config[phase].items():vals[int(k)]=v
        s=s[:m.start(1)]+json.dumps(vals)+s[m.end(1):]
    if config.get('see_order'):
        s=s.replace('def sort_moves(mb, moves, n, ply, hash_move, killers, histy):','def sort_moves(bb, mb, st, moves, n, ply, hash_move, killers, histy):').replace('sort_moves(mb,','sort_moves(bb, mb, st,')
        old='        a, b = order_key(mb, moves[i], ply, hash_move, killers, histy)\n';assert s.count(old)==1
        s=s.replace(old,old+'        if a == 1 and m_cap(moves[i]) and not m_promo(moves[i]) and see_nb(bb, mb, st, moves[i]) < 0:\n            a = 5\n')
    p.write_text(s,encoding='utf-8',newline='\n')
    chosen.append({'name':name,'source':source.relative_to(ROOT).as_posix(),'config':{'combined':[first['name'],second['name']]},'parameter_count':results[first['name']]['parameters']+results[second['name']]['parameters'],
                   'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob('*.py'))}})
for i,job in enumerate(chosen):job['lane']='confirm-a' if i%2==0 else 'confirm-b'
final={'phase':'deeper confirmation','nodes':100000,'pairs':24,'generation':chosen,'baseline':'odin_submission',
       'selection':'Complete48 games per finalist. Rank by final points; tie favors fewer changed parameters. Winner must exceed50% and pass native exact-source gates. Known stage1 results do not enter the score. These data are used to choose the final frozen candidate; only112 separate full-clock games are final strength evidence.',
       'parent_report_sha256':hashlib.sha256((HERE/'generation-report.json').read_bytes()).hexdigest(),
       'speed_optimization':'An arithmetic-equivalent fused evaluator may be applied only after equivalence and measured throughput tests; final exact-source native gate and112-game comparison include it.'}
(HERE/'finalist-policy.json').write_text(json.dumps(final,indent=2)+'\n')
with zipfile.ZipFile(HERE/'finalist-transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    z.write(HERE/'finalist-policy.json','lab/odin/fast/finalist-policy.json')
    for job in chosen:
        for p in (ROOT/job['source']).glob('*.py'):z.write(p,p.relative_to(ROOT).as_posix())
print(json.dumps({'finalists':[j['name'] for j in chosen],'games':48*len(chosen)}))
