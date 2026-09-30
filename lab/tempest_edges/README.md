# Executing the Tempest compounding plan

Read `docs/TEMPEST_COMPOUNDING_RESULTS.md` when complete, and
`docs/TEMPEST_ROUND39_REVIEW.md` for the new Gladiator loss.

Frozen research only. signer Tempest r1 is unchanged unless a later explicit
release record states otherwise. Never overwrite these sources or logs.

- `plan.json`, `stage.py`, `prototypes/`: narrower control, queen/graded depth
  alternatives, original online capture history, and TT store instrumentation.
- `probe.py`, `*-gate.jsonl`, `*-tt-linux.jsonl`, `probe-audit.json`: native
  predicates/perft/reset checks, full-history diagnostics and measured collisions.
- `stage_tt.py`, `verify_tt.py`, `bucket-native.json`: equal-memory two-slot
  cache, native collision/bound/mate/generation tests.
- `match-queen`, `match-graded`, `match-capture`, `match-bucket`: four complete
  16-game/500ms addition screens versus the narrower lazy-predicate control.
- `round39/`: legal replay and 100k, 2M and selected 12M reference searches.
- `table-inventory/`, `syzygy-data/`: current rules, source URLs, sizes and
  published checksum manifests for the 70 three/four-piece WDL and unrounded
  DTZ payloads. No engine-reference moves/evaluations are shipped as lookups.
- `syzygy_root_template.py`, `stage_tables.py`, `tablebase-verification.json`:
  original root policy, all-material outcome checks and complete conversions.
- `table_boundaries.py`, `table-boundaries.json`: mate/repetition/clock/promotion
  boundaries. The final 200 absolute plies use existing search for new coverage.
- `bundle-manifest.json`, `match-bundle`, `match-tables`: frozen exploratory
  capture/narrow/table and table-only comparisons versus released Tempest r1.
- `guard_and_deep.py`, `bundle-deep.jsonl`: actual native clock-route guard and
  longer R37/R39 probes. Search changes do not solve the R39 queen-trade error.
- `native/`: allowlisted transports and subsequent Linux exact-archive evidence.

Selected roots and used opening families are development data. The existing
12-family fresh confirmation set is reserved until a frozen candidate qualifies.
