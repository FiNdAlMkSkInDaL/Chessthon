"""Render already-completed, source-bound confirmation evidence without promotion."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
folder=HERE/'release-gates/replay25/confirmation24'
completion=json.loads((folder/'COMPLETE.json').read_text())
report=json.loads((folder/'audit.json').read_text()) if (folder/'audit.json').exists() else {}
plan=folder/'plan.json'
assert hashlib.sha256(plan.read_bytes()).hexdigest()=='fd0279a83a3ed6ebfa887dabbb2c3d282d7f811f0f80ca6149e59e9d48137a16'
if report:
    assert report['plan_sha256']==hashlib.sha256(plan.read_bytes()).hexdigest()
    assert all(hashlib.sha256((folder/n).read_bytes()).hexdigest()==h for n,h in report['log_sha256'].items())
desktop=hashlib.sha256((ROOT.parent/'agent.zip').read_bytes()).hexdigest()
lines=['# Agamemnon replay25: independent confirmation','',f"Completed: {completion['utc']}",'']
if report.get('evidence_valid'):
    s=report['statistics'];lo,hi=s['bootstrap']['score_ci']
    lines += [f"**{s['wins']} wins, {s['draws']} draws, {s['losses']} losses; score {s['score']:.2%}.**",
        f"Opening-paired95% bootstrap interval: {lo:.2%}–{hi:.2%}.",
        f"All{report['games_replayed']} games and{report['plies_replayed']} plies passed source/resource/protocol/clock/result audits.",'',
        'Bounded confirmation target: '+('PASS.' if report['bounded_confirmation_pass'] else 'NOT MET; do not claim a confirmed improvement.'),
        'This24-game reserved-family confirmation is not the112-game release guard. No automatic promotion.']
else:
    lines += ['**Evidence invalid or audit failed. No promotion.**',json.dumps(report.get('failure_reasons',completion),indent=2)]
lines += ['',f'Desktop agent.zip SHA256: `{desktop}`.',
    'Expected Tempest hash: `0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4`.',
    'The12 confirmation families are now consumed. The320 sealed Lichess roots remain untouched.',
    '', 'Evidence: `lab/agamemnon_decision/release-gates/replay25/confirmation24/`.',
    'Selection/training/blend report: `docs/AGAMEMNON_DECISION_RESULTS.md`.']
(ROOT/'docs/AGAMEMNON_CONFIRMATION_RESULTS.md').write_text('\n'.join(lines)+'\n')
report_path=ROOT/'docs/AGAMEMNON_DECISION_RESULTS.md';text=report_path.read_text()
text=text.replace('**This report is in progress while independent confirmation finishes.**','**Independent confirmation has finished; see `docs/AGAMEMNON_CONFIRMATION_RESULTS.md`.**')
text=text.replace('## Independent confirmation — running','## Independent confirmation — completed; see companion report')
report_path.write_text(text)
engineering=ROOT/'ENGINEERING.md';text=engineering.read_text()
needle='archive (`a7233886...`) passed native/protocol/resource gates and is now playing\n24 full-clock games on the12 reserved confirmation families, two VPS lanes.'
replacement='archive (`a7233886...`) passed native/protocol/resource gates and completed its\n24-game confirmation attempt. Read `docs/AGAMEMNON_CONFIRMATION_RESULTS.md`\nfor the audited result; no confirmation job remains to be launched.'
assert needle in text;text=text.replace(needle,replacement)
text=text.replace('**Agamemnon backed-up decision cycle, 6 September 2026 (in progress):**','**Agamemnon backed-up decision cycle, 6 September 2026:**')
engineering.write_text(text)
print('\n'.join(lines))
