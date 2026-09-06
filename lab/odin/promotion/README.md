# Final Odin promotion

Run this only after the exact final candidate has completed all prescribed
evidence. The default is a dry run: it validates and writes a report, without
changing Desktop ZIPs. `--apply` executes the same checks and copies the tested
bytes; it does not rebuild or upload anything.

```powershell
python -m lab.odin.promotion.promote `
  --candidate path/to/candidate-linux-x86.zip `
  --source path/to/canonical/odin `
  --plan path/to/frozen-release-plan.json `
  --gate path/to/native-gate.json `
  --primary-logs path/to/primary-a.jsonl path/to/primary-b.jsonl `
  --guard-logs path/to/guard-a.jsonl path/to/guard-b.jsonl `
  --report-dir lab/odin/promotion/reports/final
```

Add `--apply` after the dry-run review. The default Desktop path is the workspace
parent; `--desktop` can explicitly select the same actual Desktop directory.

Required checks:

- Primary: exactly40 complete colour pairs, lower95% paired-bootstrap score
  bound strictly above50%, against the frozen rules-corrected Storm control.
- Guard: exactly16 complete colour pairs, final raw score strictly above50%,
  against original Storm SHA-256 `15db92a7…e85c`. Its confidence interval remains
  diagnostic; the criterion is not changed to a stronger CI requirement.
- Every game is replayed by the existing frozen evidence validator; all faults,
  missing logs, illegal histories, clock/resource/cleanup failures and mismatched
  archive/plan/runtime/helper/referee identities reject promotion.
- Native operational evidence must match the exact candidate manifest, original
  ready state, warmed signatures, cold imports below90s, perft/deadline/cap/history
  probes and one-core/2GiB envelopes.
- The ZIP must contain flat UTF-8 Python source that parses, Unix creation
  metadata, exactly one `agent.py`, no assets/binaries and less than50MB expanded
  content. Canonical source files must match those bytes exactly; generated
  `__pycache__/*.pyc` is ignored and never packaged.
- Desktop `Storm-v4.zip` and `v3-agent.zip` must already match their known release
  hashes. An existing `agent.zip` must be original Storm or already the exact
  candidate. An existing `Odin-v5.zip` must already be the exact candidate.

On apply, both outputs are staged and hash-verified before replacement;
`Odin-v5.zip` is written before `agent.zip`. A filesystem failure can leave one
copy complete, so failure reporting names any outputs already copied. Original
Storm/v3 backup files are never changed.

Reports: `odin-release.json` contains the identity chain and both full match
audits; `ODIN_RELEASE_REPORT.md` gives the score, uncertainty and copy status.
All evidence is revalidated on every invocation. No engine is launched.

Tests:

```powershell
python -m unittest lab.odin.promotion.test_promotion -v
```
