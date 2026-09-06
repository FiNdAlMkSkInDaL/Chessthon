"""Deepen the three public same-root advantages before reporting them."""
import sys,json
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(R))
from lab.laptop_runner import apply_windows_affinity
assert apply_windows_affinity(6)['applied']
import chess,chess.engine
from lab.odin.new_games.review_new import reference
cases={c['id']:c for c in json.loads((H/'corpus-v1.json').read_text())}
selected=[r for r in json.loads((H/'summary.json').read_text())['opponent_roots'] if r['player'] in ('ms','adashima') and r['actual_minus_v6_cp']>=30]
baseline={r['id']:r for r in map(json.loads,(H/'baseline-probes.jsonl').read_text().splitlines()) if r.get('type')=='probe' and r['budget']==200000}
(H/'opponent-advantages-plan.json').write_text(json.dumps(dict(ids=[r['id'] for r in selected],nodes=2000000,selection='All ms/adashima broad roots with >=30cp advantage over 200k-node v6; deepen unrestricted and both forced moves. This is selected diagnostic confirmation, not holdout testing.'),indent=2))
exe='C:/Users/finla/AppData/Local/ChessTK/analysis-tools/stockfish-19/stockfish/stockfish-windows-arm64-universal.exe'
with chess.engine.SimpleEngine.popen_uci(exe) as e,(H/'opponent-advantages.jsonl').open('x') as out:
    e.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True})
    for r in selected:
        c=cases[r['id']];b=chess.Board(c['start_fen'])
        for u in c['history_uci']:b.push_uci(u)
        best=reference(e,b,2000000);actual=reference(e,b,2000000,[chess.Move.from_uci(c['played_uci'])]);v6=reference(e,b,2000000,[chess.Move.from_uci(baseline[r['id']]['uci'])]);sign=1 if b.turn else -1
        out.write(json.dumps(dict(**r,best_reference=best,actual_reference=actual,v6_reference=v6,deep_advantage_cp=sign*(actual['white_cp']-v6['white_cp'])))+'\n');out.flush()
print('done',len(selected))
