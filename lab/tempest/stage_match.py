"""Adapt our existing audited clock screen to explicit v6/current referee."""
import json,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];out=H/'match';out.mkdir(exist_ok=False)
manifest=[]
for name in ('clock_match.py','clock_worker.py'):
    p=R/'lab/odin/fast'/name;s=p.read_text()
    if name=='clock_match.py':
        old='outcome=b.outcome(claim_draw=True)';new='outcome=b.outcome()\n                        if outcome is None and b.is_repetition(3):outcome=chess.Outcome(chess.Termination.THREEFOLD_REPETITION,None)\n                        if outcome is None and b.is_fifty_moves():outcome=chess.Outcome(chess.Termination.FIFTY_MOVES,None)';assert s.count(old)==1;s=s.replace(old,new)
        s=s.replace('frozen112 full-clock match remains final evidence.','Current official commit284724a terminal predicates; this12-game development screen is exploratory, not promotion evidence.')
    else:
        old="assert b.is_valid() and b.outcome(claim_draw=True) is None";new="assert b.is_valid() and b.outcome() is None and not b.is_repetition(3) and not b.is_fifty_moves()";assert s.count(old)==1;s=s.replace(old,new)
    q=out/name;q.write_text(s);manifest.append(dict(source=str(p.relative_to(R)),original_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),copy_sha256=hashlib.sha256(q.read_bytes()).hexdigest()))
op=R/'lab/odin/fast/generation-openings/screen.fen'
plan=dict(candidate='lab/tempest/prototypes/pesto_only',baseline='odin_v6',candidate_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (H/'prototypes/pesto_only').glob('*.py')},baseline_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'odin_v6').glob('*.py')},openings=str(op.relative_to(R)),opening_sha256=hashlib.sha256(op.read_bytes()).hexdigest(),indices=list(range(6)),games=12,think_ms=100,cpu=4,selection='Follow-up prompted by completed candidate-set regret: PeSTO-only is 10.4cp better at1M and12.5cp at1.5s on22 non-mate roots. Use six already-used development families, both colours; do not consume fresh confirmation.',decision='Complete12 games without peeking stop. At least60% with zero faults permits a later larger confirmation; otherwise no positive playing-strength claim. This small sample cannot establish reliable Elo. No promotion.',adaptations=manifest,referee_commit='284724ab56cecb2a1a9a4e5769b4748adab4ed90')
(out/'plan.json').write_text(json.dumps(plan,indent=2));print(json.dumps(plan))
