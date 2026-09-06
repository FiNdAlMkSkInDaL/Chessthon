"""Freeze table-only and exploratory narrow/capture/table bundles."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
table=HERE/'prototypes/tablebase'
assert json.loads((HERE/'tablebase-verification.json').read_text())['audit']=='PASS'
assert json.loads((HERE/'match-capture/summary.json').read_text())['score']>=.5
allfiles={}
for name,core in [('tables_guard',ROOT/'tempest_exact/core_nb.py'),('capture_tables',HERE/'prototypes/capture/core_nb.py')]:
    out=HERE/'prototypes'/name;out.mkdir(exist_ok=False)
    for p in table.rglob('*'):
        if p.is_file():
            target=out/p.relative_to(table);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    (out/'core_nb.py').write_bytes(core.read_bytes())
    p=out/'endgame_exact.py';s=p.read_text().replace('def choose_exact(board, seen=None):','def choose_exact(board, seen=None, allow_syzygy=True):')
    s=s.replace('return original if original is not None else choose_syzygy(board, seen)','return original if original is not None else choose_syzygy(board, seen) if allow_syzygy else None')
    p.write_text(s,newline='\n')
    p=out/'agent.py';s=p.read_text();anchor='    exact = choose_exact(board, history._seen)';assert s.count(anchor)==1
    s=s.replace(anchor,'    # Preserve a clock reserve before the broader Python table probe.\n    exact = choose_exact(board, history._seen, allow_syzygy=time_left_ms >= 1200)')
    p.write_text(s,newline='\n')
    allfiles[name]={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
control=HERE/'prototypes/release';control.mkdir(exist_ok=False)
for p in (ROOT/'tempest_exact').iterdir():
    if p.is_file() and p.suffix in ('.py','.npz'):(control/p.name).write_bytes(p.read_bytes())
allfiles['release']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in control.iterdir()}
result=dict(files=allfiles,
  plan='Two 16-game 500ms development comparisons against released Tempest r1, complete pairs regardless of scores. Table-only arm isolates the coverage change. Capture/narrow/table arm is exploratory bundle selection; capture alone remained inconclusive, not promoted. At least 60% bundle score can nominate independent full-clock confirmation; no reliable Elo claim.',
  table_gate_sha256=hashlib.sha256((HERE/'tablebase-verification.json').read_bytes()).hexdigest(),
  guard='Below 1200ms retain the original three-piece DTM but decline the new 4-piece Python table route. Worst measured local policy call 281.4ms; separate Linux cold/runtime check required.')
(HERE/'bundle-manifest.json').write_text(json.dumps(result,indent=2));print('Two bundles and exact release control frozen')
