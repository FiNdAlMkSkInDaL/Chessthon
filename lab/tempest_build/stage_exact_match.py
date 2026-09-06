"""Current-rule paired smoke, source/data bound; never a large Elo claim."""
from pathlib import Path
import json,hashlib,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];out=HERE/'exact-match';out.mkdir(exist_ok=False)
for name in ('clock_match.py','clock_worker.py'):
    s=(ROOT/'lab/tempest/match'/name).read_text()
    if name=='clock_worker.py':
        s=s.replace("sorted(source.glob('*.py'))","sorted(list(source.glob('*.py'))+list(source.glob('*.npz')))")
        old="assert native_call['count']==int(b.legal_moves.count()>1),('Unexpected fallback',fen,native_call)"
        assert s.count(old)==1
        s=s.replace(old,"exact_module=sys.modules.get('endgame_exact')\n    exact_route=bool(exact_module is not None and exact_module.choose_exact(b) is not None)\n    assert native_call['count']==int(b.legal_moves.count()>1 and not exact_route),('Unexpected fallback',fen,native_call)")
        s=s.replace("return {'uci':uci,'depth':info['depth']","return {'route':'exact' if exact_route else 'search' if native_call['count'] else 'forced','uci':uci,'depth':info['depth']")
        old="if kind=='array':np.copyto(getattr(mod,name),saved)"
        assert s.count(old)==1
        s=s.replace(old,"if kind=='array':\n            current=getattr(mod,name)\n            if current.flags.writeable:np.copyto(current,saved)\n            else:assert np.array_equal(current,saved), 'Immutable module array changed'")
    else:
        s=s.replace('Current official commit284724a terminal predicates; this12-game development screen is exploratory, not promotion evidence.','Current official commit284724a. Twelve fixed short-wall smoke games; not a full-clock Elo estimate.')
    (out/name).write_text(s)
paths=[ROOT/'lab/odin/fast/generation-openings/screen.fen',ROOT/'lab/laptop_runner.py',*out.glob('*.py')]
for source in ('tempest_exact','odin_v6'):paths.extend(p for p in (ROOT/source).iterdir() if p.is_file() and p.suffix in ('.py','.npz'))
plan=dict(games=12,pairs=6,indices=list(range(6)),think_ms=100,referee='284724ab56cecb2a1a9a4e5769b4748adab4ed90',candidate='tempest_exact',baseline='odin_v6',sources={d:{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/d).iterdir() if p.is_file() and p.suffix in ('.py','.npz')} for d in ('tempest_exact','odin_v6')},decision='Complete all 12. Require zero execution/legality/reset/provenance failures; negative score rejects immediate promotion pending stronger evidence. A nonnegative score is only a smoke guard; exact-state correctness supplies the endgame improvement evidence.',opening_sha256=hashlib.sha256(paths[0].read_bytes()).hexdigest())
(out/'plan.json').write_text(json.dumps(plan,indent=2));paths.append(out/'plan.json')
with zipfile.ZipFile(out/'transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
print('12 game plan frozen')
