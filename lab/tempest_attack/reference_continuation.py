"""Equal-budget offline forced comparisons for development continuations."""
import sys,json,hashlib,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'lab/tempest_build'))
import chess,chess.engine
from review_v6_games import reference,EXE
from lab.laptop_runner import apply_windows_affinity

def main():
    assert apply_windows_affinity(8)['applied']
    cases=json.loads((HERE/'continuation-cases.json').read_text())
    # Also measure the new pressure-only candidate's unusual king move.
    opponent=json.loads((ROOT/'lab/tempest_build/day3-v6/round37-opponent-case.json').read_text())[0]
    cases.append(dict(opponent,id='r37-pressure8-Kg6',restrict='f7g6'))
    with chess.engine.SimpleEngine.popen_uci(str(EXE)) as e,(HERE/'continuation-reference-r2.jsonl').open('x') as f:
        e.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
        def emit(r):f.write(json.dumps(r)+'\n');f.flush()
        emit(dict(type='metadata',nodes=2000000,reference_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Same-root equal-node forced moves; finite reference estimates'))
        for c in cases:
            b=chess.Board(c['start_fen'])
            for u in c['history_uci']:b.push_uci(u)
            assert b.fen()==c['fen']
            r=reference(e,b,2000000,[chess.Move.from_uci(c['restrict'])] if c.get('restrict') else None)
            emit(dict(type='reference',id=c['id'],fen=b.fen(),restricted=c.get('restrict'),reference=r));print(c['id'],r.get('white_cp'),flush=True)
        emit(dict(type='complete',cases=len(cases)))
if __name__=='__main__':main()
