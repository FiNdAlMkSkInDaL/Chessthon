"""Isolated candidates for the predeclared compounding plan; never a release."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
origin=ROOT/'lab/tempest_stack/prototypes/lazy'
base=(origin/'core_nb.py').read_text()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,s):
    d=HERE/'prototypes'/name;d.mkdir(parents=True,exist_ok=False)
    for p in origin.iterdir():
        if p.is_file() and p.suffix in ('.py','.npz'):(d/p.name).write_bytes(p.read_bytes())
    if name!='control':(d/'core_nb.py').write_text(s,newline='\n')
    return {p.name:sha(p) for p in d.iterdir()}
sources={'control':save('control',base)}
anchor='            if reduction and mover % 6 == 0:'
assert base.count(anchor)==1
sources['queen']=save('queen',base.replace(anchor,'            if reduction and mover % 6 == 0 and bb[(mover // 6)*6+4]:'))
anchor='                    reduction = 0\n'
assert base.count(anchor)==1
sources['graded']=save('graded',base.replace(anchor,'                    reduction = max(0, reduction - 1)\n'))

# Capture history shares the already passed mutable history buffer. Quiet
# rows retain their exact indices. Twelve movers x six victim types add 72 rows.
s=base.replace('HISTORY = np.zeros((12, 64), dtype=np.int32)','HISTORY = np.zeros((84, 64), dtype=np.int32)')
anchor='        return np.int32(1), np.int32(-(gain * 16 - SEE_V[att_pt]))'
assert s.count(anchor)==1
s=s.replace(anchor,'''        static_rank = -(gain * 16 - SEE_V[att_pt])
        capture_rank = 0
        if m_cap(move) and not promo and att >= 0:
            capture_rank = histy[12 + att*6 + vic, m_to(move)]
        # History breaks static ties only, including at its extrema.
        return np.int32(1), np.int32(static_rank * 32769 - capture_rank)''')
s=s.replace('quiets_searched = scratch','searched_moves = scratch').replace('nquiets = 0','nrecorded = 0')
anchor='''                for q in range(nquiets):
                    failed_move = quiets_searched[q]
                    failed_piece = np.int32(mb[m_from(failed_move)])
                    history_update(histy, failed_piece, m_to(failed_move), malus)
            break
        if quiet:
            quiets_searched[nquiets] = move
            nquiets += 1'''
assert s.count(anchor)==1
s=s.replace(anchor,'''                for q in range(nrecorded):
                    failed_move = searched_moves[q]
                    if not (m_cap(failed_move) or m_promo(failed_move)):
                        failed_piece = np.int32(mb[m_from(failed_move)])
                        history_update(histy, failed_piece, m_to(failed_move), malus)
            elif m_cap(move) and not m_promo(move):
                bonus = min(1600, 32 * depth * depth)
                row = 12 + mover*6 + victim_pt(mb, move)
                history_update(histy, row, m_to(move), bonus)
                for q in range(nrecorded):
                    failed_move = searched_moves[q]
                    if m_cap(failed_move) and not m_promo(failed_move):
                        failed_piece = np.int32(mb[m_from(failed_move)])
                        row = 12 + failed_piece*6 + victim_pt(mb, failed_move)
                        history_update(histy, row, m_to(failed_move), -bonus)
            break
        searched_moves[nrecorded] = move
        nrecorded += 1''')
assert 'nquiets' not in s and 'quiets_searched' not in s
sources['capture']=save('capture',s)

# Instrument store collisions without changing replacement or search choices.
s=base.replace('TT_AGE = np.zeros(1, dtype=np.int32)','TT_AGE = np.zeros(8, dtype=np.int32)')
anchor='''    age = tta[0]
    if ttk[idx] == np.uint64(key)'''
assert s.count(anchor)==1
s=s.replace(anchor,'''    age = tta[0]
    tta[1] += 1  # store attempts
    if ttk[idx] and ttk[idx] != np.uint64(key):
        tta[2] += 1  # occupied-key collisions
        if (np.int32(ttg[idx]) >> 2) == age:
            tta[3] += 1  # current-generation collisions
            if np.int32(ttd[idx]) >= 6 and np.int32(ttd[idx]) > depth:
                tta[4] += 1  # deeper current results destroyed
            if np.int32(ttd[idx]) >= depth + 3:
                tta[5] += 1  # current results at least three plies deeper
        else:
            tta[6] += 1  # old generation replaced
    if ttk[idx] == np.uint64(key)''')
sources['tt_instrument']=save('tt_instrument',s)
plan=dict(sources=sources,baseline='control',
  first_wave=['queen','graded','capture'],
  tt_gate='Consider equal-memory two-slot buckets if at least 0.5% of store attempts evict a same-generation entry at least three plies deeper, or at least 100 depth>=6 deeper current entries are destroyed in one probe. Instrumentation must preserve exact fixed-node results.',
  game_gate='Each first-wave candidate: 16 complete development games, 8 colour pairs, 500ms search allowance, against control. Below 50% rejects further promotion testing, 50-60% inconclusive, at least 60% nominates independent confirmation. Correctness failures always block. Do not stop on running scores. Used families only; fresh confirmation remains reserved.',
  claims='Narrow control itself remains unproven; additions and combinations must eventually beat released Tempest r1 at full clocks. No archive promotion from this plan alone.')
(HERE/'plan.json').write_text(json.dumps(plan,indent=2))
# Preserve the prior review logic in a separate frozen driver for this game.
s=(ROOT/'lab/tempest_attack/review_latest.py').read_text().replace("outdir=HERE/'round38'","outdir=HERE/'round39'").replace("engine_version='Upload archive not recorded in PGN/log; version unverified'","engine_version='Tempest r1 per user attribution; PGN/log do not embed archive hash'")
(HERE/'review_loss.py').write_text(s,newline='\n')
print(json.dumps(dict(variants=list(sources),plan_sha256=sha(HERE/'plan.json'))))
