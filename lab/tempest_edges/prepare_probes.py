import hashlib,json,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
cases=json.loads((ROOT/'lab/tempest_stack/cases.json').read_text())
rows=[json.loads(s) for s in (HERE/'round39/round-39-deep.jsonl').read_text().splitlines()]
assert rows[-1]['type']=='complete'
for r in rows:
    if r['type']=='deep':
        cases.append(dict(id=f"r39-p{r['ply']}",fen=r['fen'],start_fen=r['start_fen'],history_uci=r['history_uci'],storm_colour=r['own_colour'],budgets=[200000],reference_best=r['best'],reference_played=r['played'],played_uci=r['played_uci']))
assert len({c['id'] for c in cases})==len(cases)
(HERE/'gate-cases.json').write_text(json.dumps(cases,indent=2))
ttcases=cases[:4]
for c in ttcases:c['budgets']=[1000000,4000000]
(HERE/'tt-cases.json').write_text(json.dumps(ttcases,indent=2))
launch='''#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-edges-probe-r1"
PY="$HOME/chess-tk/.venv/bin/python"
"$PY" -B lab/tempest_edges/probe.py --variant control --cpu 0 --cases lab/tempest_edges/tt-cases.json --tag tt-linux > lab/tempest_edges/tt-a.stdout 2> lab/tempest_edges/tt-a.stderr &
A=$!
"$PY" -B lab/tempest_edges/probe.py --variant tt_instrument --cpu 1 --cases lab/tempest_edges/tt-cases.json --tag tt-linux > lab/tempest_edges/tt-b.stdout 2> lab/tempest_edges/tt-b.stderr &
B=$!
RA=0; RB=0
wait "$A" || RA=$?
wait "$B" || RB=$?
test "$RA" -eq 0 && test "$RB" -eq 0
'''
(HERE/'probe-launch.sh').write_text(launch,newline='\n')
paths=[HERE/'probe.py',HERE/'tt-cases.json',HERE/'plan.json',HERE/'probe-launch.sh',ROOT/'lab/perft.py',ROOT/'lab/laptop_runner.py']
for name in ('control','tt_instrument'):paths+=list((HERE/'prototypes'/name).iterdir())
with zipfile.ZipFile(HERE/'probe-transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
print(json.dumps(dict(gate_roots=len(cases),tt_roots=len(ttcases))))
