"""Freeze a 2x2 search-identity and throughput experiment, not a release."""
import hashlib
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
origin = ROOT / 'lab/tempest_attack/prototypes/pawn_lmr'
original = (origin / 'core_nb.py').read_text()
start = original.index('        # A quiet pawn push near the enemy king')
end = original.index('\n        if (', start)
lazy = original[:start] + original[end:]
assert lazy.count('            and not pawn_threat\n') == 1
lazy = lazy.replace('            and not pawn_threat\n', '')
anchor = '            reduction = quiet_reduction(depth, searched, is_pv, move_history)'
assert lazy.count(anchor) == 1
lazy = lazy.replace(anchor, anchor + '''
            # Same exemption, evaluated only for an otherwise reduced move.
            # A quiet pawn push cannot change the opposing king's square.
            if reduction and mover % 6 == 0:
                ek = lsb(bb[(1 - mover // 6)*6+5])
                target = m_to(move)
                if abs((target&7)-(ek&7)) <= 1 and abs((target>>3)-(ek>>3)) <= 3:
                    reduction = 0
''')
sort_start = original.index('    keys0 = np.empty(n, dtype=np.int32)', original.index('def sort_moves('))
sort_end = original.index('\n\n\n@njit', sort_start)
old_sort = original[sort_start:sort_end]
new_sort = '''    # Preserve the exact stable lexicographic order of two signed int32s.
    # Categories are 0..4; offsetting the low word prevents signed carry.
    keys = np.empty(n, dtype=np.int64)
    for i in range(n):
        a, b = order_key(mb, moves[i], ply, hash_move, killers, histy)
        keys[i] = np.int64(a) * 4294967296 + np.int64(b) + 2147483648
    for i in range(1, n):
        mv = moves[i]
        key = keys[i]
        j = i
        while j > 0 and keys[j - 1] > key:
            moves[j] = moves[j - 1]
            keys[j] = keys[j - 1]
            j -= 1
        moves[j] = mv
        keys[j] = key'''
sources = {}
for name, text in [('narrow', original), ('lazy', lazy), ('packed', original.replace(old_sort, new_sort)), ('both', lazy.replace(old_sort, new_sort))]:
    out = HERE / 'prototypes' / name
    out.mkdir(parents=True, exist_ok=False)
    for p in origin.iterdir():
        if p.is_file() and p.suffix in ('.py', '.npz'):
            (out / p.name).write_bytes(p.read_bytes())
    if name != 'narrow':
        (out / 'core_nb.py').write_text(text, newline='\n')
    sources[name] = {p.name: sha(p) for p in out.iterdir()}

cases = json.loads((ROOT/'lab/tempest_build/day3-v6/round37-probe-cases.json').read_text())
cases += json.loads((ROOT/'lab/tempest_build/day3-v6/round37-opponent-case.json').read_text())
cases += [c for c in json.loads((ROOT/'lab/tempest/corpus-v1.json').read_text()) if c['source_kind']=='own-known']
for c in cases:
    c['budgets'] = [200000]
(HERE/'cases.json').write_text(json.dumps(cases, indent=2))
plan = dict(sources=sources, cases_sha256=sha(HERE/'cases.json'),
    variants=['narrow','lazy','packed','both'], repeats=2, nodes=200000,
    lanes={'a': ['narrow','lazy','packed','both'], 'b': ['both','packed','lazy','narrow']},
    decision='Require identical legal move, score, depth and node count on every fixed-node run; stable ordering parity and perft must pass. Throughput is Linux development evidence, not Elo. A speed claim requires a positive geometric-mean effect in both lane orders, and deployment needs separate full-clock gates. No source or Desktop promotion in this experiment.',
    scope='Used selected diagnostic roots, not independent tactical holdout. Two pinned Linux cores, mirrored candidate order. All trials complete regardless of timing.')
(HERE/'plan.json').write_text(json.dumps(plan, indent=2))
launch = '''#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-stack-r1"
PY="$HOME/chess-tk/.venv/bin/python"
(for V in narrow lazy packed both; do taskset -c 0 "$PY" -B lab/tempest_stack/bench.py --variant "$V" --lane a; done) > lab/tempest_stack/lane-a.stdout 2> lab/tempest_stack/lane-a.stderr &
A=$!
(for V in both packed lazy narrow; do taskset -c 1 "$PY" -B lab/tempest_stack/bench.py --variant "$V" --lane b; done) > lab/tempest_stack/lane-b.stdout 2> lab/tempest_stack/lane-b.stderr &
B=$!
RA=0; RB=0
wait "$A" || RA=$?
wait "$B" || RB=$?
test "$RA" -eq 0 && test "$RB" -eq 0
'''
(HERE/'launch.sh').write_text(launch, newline='\n')
paths = list(HERE.glob('*.py')) + [HERE/'cases.json', HERE/'plan.json', HERE/'launch.sh', ROOT/'lab/perft.py', ROOT/'lab/laptop_runner.py']
for d in (HERE/'prototypes').iterdir(): paths += list(d.iterdir())
with zipfile.ZipFile(HERE/'transport.zip', 'x', zipfile.ZIP_DEFLATED) as z:
    for p in paths: z.write(p, p.relative_to(ROOT).as_posix())
print(json.dumps(dict(variants=4, roots=len(cases), transport_sha256=sha(HERE/'transport.zip'))))
