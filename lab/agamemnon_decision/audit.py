"""Independent corpus/variation/checkpoint audit; never reads sealed root contents."""
import json,hashlib,collections
from pathlib import Path
import chess,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def canonical(b):return min(' '.join(b.fen().split()[:4]),' '.join(b.mirror().fen().split()[:4]))
def main():
    roots=[json.loads(l) for l in (HERE/'data/roots.jsonl').read_text().splitlines()];assert len(roots)==2880
    for field in ('id','game_id','family','key'):assert len({r[field] for r in roots})==2880
    stats=collections.Counter();divergence=collections.Counter();hashes={}
    for path in sorted((HERE/'settled').glob('lane*.jsonl')):
        records=[json.loads(l) for l in path.read_text().splitlines()];assert records[-1]['type']=='complete';hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        for r in records:
            if r.get('type')!='root':continue
            b=chess.Board(r['start_fen'])
            for u in r['history_uci']:b.push_uci(u)
            assert b.fen()==r['fen'];stats['roots']+=1
            for alt in r['alternatives']:
                own,teacher=alt['own'],alt['reference'];leaf=b.copy();ref=b.copy();stats['alternatives']+=1
                assert teacher['bound']=='unbounded_completed_iteration' and teacher['uci']==own['uci']
                for u in teacher['pv']:ref.push_uci(u)
                stats['teacher_pvs_legal']+=1
                if not own['provenance']:continue
                for u in own['pv']:leaf.push_uci(u)
                assert leaf.fen()==own['leaf_fen'] and own['pv'][0]==own['uci']
                assert own['score']==own['leaf_value_white']*(1 if b.turn else -1)
                assert not leaf.is_check() and not leaf.is_game_over()
                actual_quiet=not any(leaf.is_capture(m) or m.promotion for m in leaf.legal_moves);assert actual_quiet==own['quiet']
                stats['own_pvs_legal']+=1;stats['beta_cutoff']+=int(own['stand_cutoff']);stats['capture_free']+=int(own['quiet']);stats['leaf_halfmove_ge80']+=int(leaf.halfmove_clock>=80)
                common=0
                for x,y in zip(own['pv'],teacher['pv']):
                    if x!=y:break
                    common+=1
                divergence['same_first_opponent_reply' if common>=2 else 'different_first_opponent_reply']+=1
    assert stats['roots']==2880 and stats['alternatives']==12293 and stats['own_pvs_legal']==11927 and stats['beta_cutoff']==0
    splitkeys={0:set(),1:set()}
    for r in map(json.loads,(HERE/'dataset-settled/leaves.jsonl').read_text().splitlines()):splitkeys[r['split']].add(canonical(chess.Board(r['leaf_fen'])))
    assert not splitkeys[0]&splitkeys[1]
    # Snapshot reproduction is expected bit-exact for saved best checkpoints.
    reproductions=[]
    for p in (HERE/'fits-full').glob('*-snapshots/model.npz'):
        original=p.parent.with_name(p.parent.name.removesuffix('-snapshots'))/'model.npz';a=np.load(p);b=np.load(original);assert a.files==b.files and all(np.array_equal(a[k],b[k]) for k in a.files);reproductions.append(p.parent.name)
    release=hashlib.sha256((ROOT.parent/'agent.zip').read_bytes()).hexdigest();assert release=='0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4'
    report=dict(stats=dict(stats),teacher_pv_divergence=dict(divergence),cross_split_leaf_keys_disjoint=True,reproductions=reproductions,source_hashes=hashes,desktop_sha256=release,sealed_roots_read=False,scope='Full legal replay and recorded score-perspective audit; teacher PV divergence is diagnostic, not a model-strength claim. Sealed320 roots were not opened.')
    (HERE/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
