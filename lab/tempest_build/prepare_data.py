"""Freeze unused family-grouped roots before sampling or fitting any model."""
import hashlib,io,json,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import chess,chess.pgn
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def key(b):return ' '.join(b.fen(en_passant='legal').split()[:4])
def phase(b):return min(24,sum(len(b.pieces(pt,c))*w for pt,w in [(2,1),(3,1),(4,2),(5,4)] for c in (True,False)))
def main():
    out=HERE/'data';out.mkdir(exist_ok=False)
    used_families=set();known=set();sources=[]
    paths=[ROOT/'lab/odin/training/corpus-20k.jsonl',ROOT/'lab/odin/quiet_eval/fit-records.jsonl']
    paths+=list((ROOT/'lab/odin/release_openings').glob('*.jsonl'))
    paths+=list((ROOT/'lab/odin/fast').glob('*openings/*.jsonl'))
    paths+=[ROOT/'lab/tempest/fresh-confirmation/openings.jsonl']
    for p in paths:
        if p.name in ('candidate-pool.jsonl','reference.jsonl'):continue
        sources.append(dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        for line in p.read_text().splitlines():
            r=json.loads(line)
            if r.get('opening_position_key'):used_families.add(r['opening_position_key'])
            if r.get('opening_key'):
                b=chess.Board()
                try:
                    for u in r['opening_key'].split():b.push_uci(u)
                    used_families.add(key(b))
                except ValueError:pass
            if r.get('fen'):known.add(key(chess.Board(r['fen'])))
    games=list((ROOT/'Chess_results_day1').glob('*.pgn'))+list((ROOT/'chess_results_day2').glob('*.pgn'))+list((ROOT/'Chess_results_day3').glob('*.pgn'))+list((ROOT/'lab/tempest/public').glob('*.pgn'))
    for p in games:
        with p.open(encoding='utf-8-sig') as f:g=chess.pgn.read_game(f)
        if g:
            b=g.board();known.add(key(b))
            for m in g.mainline_moves():b.push(m);known.add(key(b))
    for p in (ROOT/'lab/odin/native_release/odin-v6-architecture-r1/overnight112').glob('primary-?.jsonl'):
        for line in p.open():
            r=json.loads(line)
            if not r.get('pgn'):continue
            g=chess.pgn.read_game(io.StringIO(r['pgn']));b=g.board();known.add(key(b))
            for m in g.mainline_moves():b.push(m);known.add(key(b))
    candidates=[];raw_manifest=[]
    for p in sorted((ROOT/'lab/odin/training/raw').glob('*.pgn')):
        raw_manifest.append(dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        with p.open(encoding='utf-8-sig',errors='replace') as f:
            gi=0
            while (g:=chess.pgn.read_game(f)) is not None:
                gi+=1
                if g.errors or g.headers.get('SetUp')=='1':continue
                moves=list(g.mainline_moves());b=g.board();family=None;choices=[];history=[]
                for ply,m in enumerate(moves):
                    b.push(m);history.append(m.uci())
                    if ply==7:family=key(b)
                    if family in used_families:break
                    if ply<15 or ply%6!=3 or not family or b.is_game_over() or b.halfmove_clock>70 or len(b.piece_map())<5 or key(b) in known:continue
                    ph=phase(b);group='endgame' if ph<=6 else 'middle' if ph<=17 else 'high'
                    rank=digest('tempest-data-v1'+p.name+str(gi)+str(ply))
                    choices.append(dict(id=rank[:20],fen=b.fen(),start_fen=g.board().fen(),history_uci=history.copy(),family=family,phase=ph,group=group,source_game=f'{p.name}:{gi}',source_ply=ply+1,selection_rank=rank))
                # At most two roots per human game, preserving grouped splits.
                candidates.extend(sorted(choices,key=lambda r:r['selection_rank'])[:2])
    candidates.sort(key=lambda r:r['selection_rank']);counts=collections.Counter();families=collections.Counter();selected=[];positions=set()
    quota={'endgame':650,'middle':700,'high':650}
    for r in candidates:
        k=key(chess.Board(r['fen']))
        if counts[r['group']]>=quota[r['group']] or families[r['family']]>=4 or k in positions:continue
        n=int(digest('tempest-split-v1'+r['family'])[:8],16)%10
        r['split']='test' if n==0 else 'validation' if n==1 else 'train'
        selected.append(r);counts[r['group']]+=1;families[r['family']]+=1;positions.add(k)
        if len(selected)==2000:break
    assert len(selected)>=500,(len(selected),counts)
    manifest=dict(requested_roots=2000,actual_roots=len(selected),phase_counts=dict(counts),split_counts=dict(collections.Counter(r['split'] for r in selected)),families=len(families),excluded_families=len(used_families),excluded_positions=len(known),exclusion_sources=sources,raw_sources=raw_manifest,scope='New human-game roots; no self-play tranche yet. Search states are generated later. Groups fixed before labels; test withheld from selection.',script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'roots.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected))
    manifest['roots_sha256']=hashlib.sha256((out/'roots.jsonl').read_bytes()).hexdigest()
    (out/'split-manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps({k:manifest[k] for k in ('actual_roots','phase_counts','split_counts','families')}))
if __name__=='__main__':main()
