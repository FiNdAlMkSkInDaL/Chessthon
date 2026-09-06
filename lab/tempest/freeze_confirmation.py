"""Candidate-blind fresh-family confirmation; balance analysis only, no v6 queries."""
import json,sys,hashlib,io,collections
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(R))
import chess,chess.pgn,chess.engine
from lab.odin.release_openings.build import known_positions,bkey
from lab.odin.new_games.review_new import reference
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(8)['applied']
def main():
    out=H/'fresh-confirmation';out.mkdir(exist_ok=False);known,known_files=known_positions();used=set();exclusions=[]
    paths=[p for p in (R/'lab/odin/release_openings').glob('*.jsonl') if p.name!='candidate-pool.jsonl']+list((R/'lab/odin/fast').glob('*openings/*.jsonl'))
    for p in paths:
        if p.name=='reference.jsonl':continue
        for s in p.read_text().splitlines():
            r=json.loads(s)
            if r.get('opening_position_key'):used.add(r['opening_position_key'])
        exclusions.append(dict(path=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    for p in list((R/'Chess_results_day3').glob('*.pgn'))+list((H/'public').glob('*.pgn')):
        g=chess.pgn.read_game(io.StringIO(p.read_text(encoding='utf-8-sig')));b=g.board();known.add(bkey(b))
        for m in g.mainline_moves():b.push(m);known.add(bkey(b))
    for p in (R/'lab/odin/native_release/odin-v6-architecture-r1/overnight112').glob('primary-?.jsonl'):
        for s in p.open():
            r=json.loads(s)
            if 'pgn' not in r:continue
            g=chess.pgn.read_game(io.StringIO(r['pgn']));b=g.board();known.add(bkey(b))
            for m in g.mainline_moves():b.push(m);known.add(bkey(b))
    poolpath=R/'lab/odin/release_openings/candidate-pool.jsonl';pool=[json.loads(s) for s in poolpath.read_text().splitlines()];pool.sort(key=lambda r:hashlib.sha256(('tempest-confirm-v1'+r['id']).encode()).hexdigest())
    plan=dict(seed='tempest-confirm-v1',quota={'e4':4,'d4':4,'flank':4},max_abs_cp=80,nodes=100000,pool_sha256=hashlib.sha256(poolpath.read_bytes()).hexdigest(),excluded_families=len(used),known_positions=len(known),exclusion_files=exclusions,purpose='12 paired confirmation openings for a future frozen candidate. Not sufficient for decisive promotion. No engine/candidate searches conducted here; labels used only to balance starts.')
    (out/'plan.json').write_text(json.dumps(plan,indent=2));selected=[];counts=collections.Counter()
    exe='C:/Users/finla/AppData/Local/ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe'
    with chess.engine.SimpleEngine.popen_uci(exe) as e,(out/'balance.jsonl').open('x') as log:
        e.configure({'Threads':1,'Hash':64})
        for r in pool:
            if r['opening_position_key'] in used or counts[r['group']]>=4 or bkey(chess.Board(r['fen'])) in known:continue
            ref=reference(e,chess.Board(r['fen']),100000);ok=abs(ref['white_cp'])<=80 and ref.get('white_mate') is None
            log.write(json.dumps(dict(id=r['id'],accepted=ok,reference=ref))+'\n');log.flush()
            if ok:selected.append(r);used.add(r['opening_position_key']);counts[r['group']]+=1
            if len(selected)==12:break
    assert len(selected)==12,counts
    (out/'openings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected));(out/'openings.fen').write_text('\n'.join(r['fen'] for r in selected)+'\n')
    (out/'manifest.json').write_text(json.dumps(dict(counts=dict(counts),n=12,fen_sha256=hashlib.sha256((out/'openings.fen').read_bytes()).hexdigest(),candidate_unsearched=True),indent=2));print('frozen',dict(counts))
if __name__=='__main__':main()
