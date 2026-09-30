# Tempest attack and move-ordering research

Read `docs/TEMPEST_FRONTIER_RESEARCH.md` from the workspace root. signer
`agent.zip` is still released Tempest r1; nothing here is promoted.

- `features.py`, `fit.py`, `fit/`: original attack-coordination residual,
  constrained fit, all six trials and family-blocked development predictions.
- `prototypes/`: isolated exact-source candidates; never overwrite these to
  rerun an experiment. `baseline`, `cap1600`, `pressure8`, `pawn_threat`,
  `pawn_lmr`, `pawn_ff`, `policy_cheap` are distinct variants.
- `*-trace-r2.jsonl`, `*-trace-wall.jsonl`: complete isolated diagnostic probes.
  Initial non-r2 traces stopped in setup on a lab uint64 conversion error.
- `continuation-cases.json`, `baseline-trace-continuation.jsonl`,
  `continuation-reference-r2.jsonl`: forced continuation comparisons with full
  history. TT tails after aborted iterations are not certified PVs.
- `trace_search_v5.py`, `deep-cases.json`, `*-trace-linux-deep.jsonl`: frozen
  Linux 1M/4M/9,432,064-node tests. The one-million-node Qc2 improvement did not
  survive larger budgets.
- `match/`, `match-lmr/`: completed source-bound 16-game paired screens and
  independent replay audits. The former failed; the latter was inconclusive.
- `round38/`: full RMFE draw review, four deep comparisons, and all 101
  five-piece tablebase responses. Reference lookup data is lab-only.
- `policy_prior.py`, `policy/`: original conditional quiet-move ranker, all
  trials, feature matrix and grouped used-family folds.
- `policy_cheap.py`, `policy-cheap/`: two cost-ablation fits, collapsed small
  coefficient matrix and explicit model-selection gate.
- `stage_policy.py`, `policy-native-manifest.json`, `verify_policy.py`,
  `policy-native-verification.json`: native integration, parity and priorities.
- `match-policy/`: completed 16-game/500ms comparison with Tempest r1,
  2W/11D/3L, failed promotion screen; all game replays and identities pass.

Run with the existing Python 3.12 environment. Data-producing scripts generally
create output paths exclusively; never delete completed evidence to rerun.
`stage_match.py` and `audit_match.py` take explicit named experiment arguments.
Remote credentials are not part of any transport, source directory or report.

All earlier pilot splits used here are development data. The previous fresh
confirmation families remain separate. A successful classifier is not an Elo
result, and a 500ms search allowance is not a 120+0.5 game-clock test.
