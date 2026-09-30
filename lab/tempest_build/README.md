# Tempest implementation evidence

Start with `docs/TEMPEST_R1_RELEASE.md` and
`docs/TEMPEST_IMPLEMENTATION_STATUS.md`. Current released source is
`tempest_exact/`; `tempest/` is the rules-only fallback; `odin_v6/` is preserved.
Nothing in this lab is imported by the submission except the explicitly copied
`endgame_exact.py` and the original generated `three_piece_dtm.npz` data.

Use Python 3.12:
`python`.
Scripts that create experiment directories/logs use exclusive creation. Do not
delete old evidence to rerun them; use a separate workspace/output copy.

## Evidence map

- `setup.py`, `setup-manifest.json`, `public/`, `official-284724ab/`: exact source
  isolation and re-fetched official rules/starter. Official harness is untouched.
- `test_rules.py`, `rules-test.json`: native actual-fifty/terminal precedence,
  current-referee scripted games, cap boundaries and perft.
- `day3-v6/`: complete rounds 35–37 references, full history, source identities,
  same-root deep checks and 27 selected v6/LMR-off/futility-off probes for the
  new Neural Gambit loss. No game data here was used to fit the pilot.
- `prepare_data.py`, `data/roots.jsonl`, `data/split-manifest.json`: 1,131 roots
  from 578 unused opening families; source-game correlation caps and frozen
  whole-family train/validation/test partitioning.
- `stage_sampler.py`, `sampler-source/`, `sampler-manifest.json`,
  `sample_search.py`: offline-only native leaf instrumentation. Existing search
  node/deadline slots are untouched; additional buffer slots carry path/sample
  data. No per-node Python callbacks. Null-search paths are excluded.
- `data/control-probes.jsonl`, `sampler-probes.jsonl`, `sampler-identity.json`:
  30 equal-node identity controls and A–B–A isolation proofs.
- `data/search-states.jsonl`, `states.jsonl`, `labels-plan.json`, `labels-?.jsonl`:
  all 5,754 legal states and independent 200k-node reference labels, supplied
  full stored history and cleared hash. Each shard has a completion record.
- `fit_pilot.py`, `pilot/`: six original neural configurations and the linear
  control, frozen model-selection rule, exact data hashes, predictions, weights,
  all reported results and a subsequent grouped linear-error diagnostic.
  **Neither model is deployed.** `pilot-setup-only-symmetry-check/` preserves a
  setup assertion caught before fitting; sorted feature IDs corrected it.
- `mate_analysis.py`, `mate-conversion*.jsonl`: short-wall and fixed-node
  diagnostics of stopping at mate scores. Fixed-node conversion lengths were
  identical for both policies. No clock change was accepted.
- `generate_three_piece.py`, `three-piece/generation.json`: original exhaustive
  retrograde KQK/KRK generator, source hash, state counts and maximum distances.
  No reference engine or third-party tablebase supplied the data.
- `verify_three_piece.py`, `three-piece/verification.json`: every legal state
  and forward edge satisfies the terminal/minimax-distance recurrence using the
  existing independently tested native move generator; 4,000 python-chess
  legal-set cross-checks.
- `test_exact_policy.py`, `three-piece/policy-test.json`: 640 complete
  conversions, both attacker colors, capture-for-draw, unsupported material,
  root preservation, fifty-move and absolute-ply mate precedence.
- `three-piece/linux-regeneration-identity.json`: native regeneration yields
  exactly the same arrays and uncompressed NPY entries. The NPZ container hash
  differs by platform, so the tested archive retains its original bound data.
- `stage_exact.py`, `exact-manifest.json`: only approved source/data copied into
  the endgame candidate. `pack_exact_linux.py` packs and verifies it on Linux.
- `exact-match/`: frozen short-smoke plan, source/data hashes, original failed
  setup and corrected transport, both completed lanes and full legal replay
  audit. The immutable-array reset fix affects lab workers only.
- `audit_fullclock.py`: retains the existing source/resource/clock validator's
  game checks while adapting its historical intended-claim predicate in memory
  to the current official rule. No old audit source or evidence is rewritten.
- `lab/odin/native_release/tempest-exact-r1/` (outside this directory): Linux
  archive, native gate, member manifest, signer release record, full-clock
  smoke logs/audit. `promote_exact.py` checks archive/source identities and
  preserves Odin v6 before atomically replacing the signer archive (not in git).

## Useful reproduction commands

Read each script's output-path behavior before launching. These commands ran
the completed experiments; existing output files intentionally prevent some
from being repeated in place:

```powershell
$py = 'python'
& $py -B lab/tempest_build/test_rules.py
& $py -B lab/tempest_build/verify_three_piece.py
& $py -B lab/tempest_build/test_exact_policy.py
& $py -B lab/tempest_build/audit_exact_match.py
& $py -B lab/tempest_build/audit_fullclock.py
```

For an independent table regeneration, import the unchanged generator in a
short Python script, set its `HERE` to a new empty output parent, then call
`main()`. Compare the loaded `queen` and `rook` arrays to the shipped data;
do not use a platform-dependent NPZ container hash as the only equivalence test.

The implementation intentionally did not consume the 12 reserved fresh
confirmation opening families or start another 112-game strength test for a
failed evaluator. All inspected training-test examples are now used data for
future model selection; a future decisive evaluation needs fresh families.
