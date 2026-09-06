"""Structural experiment: response-conditioned history for ordering and LMR."""
import json,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
out=ROOT/'odin_continuation';out.mkdir(exist_ok=False)
for p in (ROOT/'odin_submission').glob('*.py'):shutil.copy2(p,out/p.name)
p=out/'core_nb.py';s=p.read_text(encoding='utf-8')
s=s.replace('HISTORY = np.zeros((12, 64), dtype=np.int32)','HISTORY = np.zeros((780, 768), dtype=np.int32)')
s=s.replace('np.zeros((MAX_PLY, 7), dtype=np.uint64)','np.zeros((MAX_PLY, 8), dtype=np.uint64)')
where=s.index('@njit(cache=False)\ndef sort_moves(')
helper='''@njit(cache=False)
def continuation_row(mb, undos, ply):
    # The previous move is known inside search. Nothing is inferred from FENs.
    if ply <= 0 or undos.shape[1] < 8:
        return -1
    if undos[ply - 1, U_CAP] == np.uint64(13):
        return -1
    previous = np.int32(undos[ply - 1, 7])
    if previous == 0:
        return -1
    square = m_to(previous)
    piece = np.int32(mb[square])
    if piece < 0:
        return -1
    return 12 + piece * 64 + square


'''
s=s[:where]+helper+s[where:]
s=s.replace('def sort_moves(mb, moves, n, ply, hash_move, killers, histy):','def sort_moves(mb, moves, n, ply, hash_move, killers, histy, context=-1):')
old='        a, b = order_key(mb, moves[i], ply, hash_move, killers, histy)\n';assert s.count(old)==1
s=s.replace(old,old+'''        if a == 4 and context >= 0:
            piece = np.int32(mb[m_from(moves[i])])
            b -= histy[context, piece * 64 + m_to(moves[i])] // 2
''')
old='    sort_moves(mb, moves_buf, n, ply, hash_move, killers, histy)';assert s.count(old)==2
s=s.replace(old,'    context = continuation_row(mb, undos, ply)\n'+old[:-1]+', context)')
old='        make_nb(bb, mb, st, move, undos[ply])\n';assert s.count(old)==2
s=s.replace(old,old+'        if undos.shape[1] >= 8:\n            undos[ply, 7] = np.uint64(move)\n')
old='        make_nb(bb, mb, st, move, undos[0])\n';assert s.count(old)==1
s=s.replace(old,old+'        if undos.shape[1] >= 8:\n            undos[0, 7] = np.uint64(move)\n')
old='        move_history = histy[mover, m_to(move)] if quiet else 0\n';assert s.count(old)==1
s=s.replace(old,old+'        if quiet and context >= 0:\n            move_history += histy[context, mover * 64 + m_to(move)] // 2\n')
old='            cutoff_quiet(mb, move, depth, ply, killers, histy)\n';assert s.count(old)==1
s=s.replace(old,old+'            if quiet and context >= 0:\n                history_update(histy, context, mover * 64 + m_to(move), min(1600, 32 * depth * depth))\n')
old='                    history_update(histy, failed_piece, m_to(failed_move), malus)\n';assert s.count(old)==1
s=s.replace(old,old+'                    if context >= 0:\n                        history_update(histy, context, failed_piece * 64 + m_to(failed_move), malus)\n')
p.write_text(s,encoding='utf-8',newline='\n')
p=out/'agent.py';p.write_text(p.read_text(encoding='utf-8').replace('Odin v5.','Odin continuation experiment.'),encoding='utf-8',newline='\n')
policy={'generation':[{'name':'continuation','source':'odin_continuation','lane':'windows-continuation','config':{'continuation_history':True},'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.py'))}}],
        'stage1':{'pairs':9,'nodes':20000},'selection':'Additional structural probe while the four previously frozen finalists complete. Reuses known generation starts, so it is development only. Extend deeper testing only if this scores at least12/18 points with zero faults and isolation passes. Otherwise it does not delay the overnight winner. No automatic promotion.'}
(HERE/'continuation-policy.json').write_text(json.dumps(policy,indent=2)+'\n');print(json.dumps({'source':str(out),'feature':'Response-conditioned quiet history, used in ordering and reductions. 2.4MB native table, bounded gravity updates, no persistent external data.'}))
