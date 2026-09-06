"""Check new split identities, disjoint families, replay and frozen reference selection."""
import hashlib,json,sys
from pathlib import Path
import chess
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from lab.odin.release_openings.build import known_positions,bkey
old=ROOT/'lab/odin/release_openings'
previous=[json.loads(s) for n in ('development','holdout') for s in (old/(n+'.jsonl')).read_text().splitlines()]
known,sources=known_positions();seen={r['opening_position_key'] for r in previous}
manifest={}
for split,count in [('screen',24),('overnight',56)]:
    out=HERE/(split+'-openings');rows=[json.loads(s) for s in (out/'openings.jsonl').read_text().splitlines()]
    refs={r['id']:r for r in [json.loads(s) for s in (out/'reference.jsonl').read_text().splitlines()]}
    fens=(out/'openings.fen').read_text().splitlines();assert len(rows)==count and fens==[r['fen'] for r in rows]
    for r in rows:
        assert r['opening_position_key'] not in seen;seen.add(r['opening_position_key'])
        b=chess.Board()
        for uci in r['prefix_uci']:b.push_uci(uci)
        assert b.fen()==r['fen'] and b.is_valid() and b.outcome(claim_draw=True) is None
        assert bkey(b) not in known
        ref=refs[r['id']];assert ref['accepted'] and abs(ref['reference']['white_cp'])<=80 and ref['reference'].get('white_mate') is None
    manifest[split]={'positions':count,'all_unique_families':True,'prefix_replay':True,'known_position_overlap':0,
                     'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}}
result={'pass':True,'previous_families_excluded':len(previous),'known_positions':len(known),'new_splits':manifest,
        'training_exclusions':'Inherited from audited candidate pool; all80 selected openings additionally replayed and checked against current known site positions.'}
(HERE/'opening-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
