# Odin v6 released — 6 September 2026

**Current release:** Desktop `agent.zip` and `Odin-v6.zip` contain the exact
Linux archive `cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647`.
All112 overnight games audited PASS: **30W/69D/13L,57.59%**, paired95% interval
52.23–62.95%, no operational failures. V5 is preserved as `Odin-v5.zip`.
Read [ODIN_V6_RELEASE_REPORT.md](ODIN_V6_RELEASE_REPORT.md) and
[ODIN_DAY3_REVIEW.md](ODIN_DAY3_REVIEW.md). No site upload was performed.
The earlier progress entries below are historical.

**New overnight test, 5 September 23:30 UTC:** the user subsequently authorized
a fresh 112-game comparison for one more iteration. Odin v6's architecture
candidate is now running against released v5 in two persistent VPS lanes.
This does not resume the cancelled R10 test described below. See
[ODIN_V6_MORNING_REVIEW.md](ODIN_V6_MORNING_REVIEW.md) for exact artifacts,
evidence, active services and morning instructions. Desktop `agent.zip`
remains v5 pending that review.

**Current status,5 September2026:** Desktop `agent.zip` and `Odin-v5.zip` now
contain the exact tested Linux R10 archive, SHA-256
`c7d8972e823eb821c016010445d4b02996daff954d870d63083c445850e21102`.
Canonical source: `odin_submission/`. Original Storm/v3 backups are preserved.
No website upload was performed.

The user explicitly rejected waiting5–6 more hours for112 games. Both lanes
were stopped after their current complete pairs: **16 games,9W/2D/5L,62.5%**
against the minimally current-rules-corrected Storm control, zero operational
failures. Every game passed legal replay, source, clock and resource checks;
the exact archive passed all native import/protocol/perft/deadline and state
gates. This is a practical expedited release, **not a passed95% confidence
gate**. The original80+32 plan was not completed; the original-Storm32-game
guard and queued optional Linux diagnostics were cancelled. Original plans
and interrupted logs remain intact. No game result was removed or relabelled.

All chess test controllers, the old automatic finalizer and its temporary
awake helper have stopped. The `STOP-FINALIZATION` marker remains to prevent
the old workflow from being resumed accidentally. Release evidence:
`lab/odin/promotion/reports/expedited-r10/ODIN_RELEASE_REPORT.md` and its JSON.
Promotion code: `lab/odin/promotion/expedited_release.py`. The approved faster
iteration direction is documented in `docs/FAST_ITERATION_PROTOCOL.md`;
the reusable warm-worker harness is a future implementation, not shipped code.

The remainder records historical work and is superseded by this release.

# Historical release work

Updated 5 September 2026, final test launch. Desktop `agent.zip` is still
released Storm v4. Positional R7 completed **6W/1D/1L, zero faults** at
60,000+500 in four development color pairs. The selected release is the
behavior-equivalent cleaned R10 source, `odin_submission/`, Linux ZIP hash
`c7d8972e823eb821c016010445d4b02996daff954d870d63083c445850e21102`.
R10 passed its exact-archive native gate, constrained SEE/EP/warmup/15 fifty
cases (32.22s import,149ms first call), and3,857-state/9,503-edge differential.
No new root signature appeared after import. Exact threefold search predicates
are deliberately not claimed: this lineage retains Storm's cycle heuristic.

The **112-game final plan is frozen**, SHA-256
`26551be568a8e2fc7eaeb60530fd2c3934c86c8056021c7db840e7414c686734`,
under `lab/odin/native_release/odin-release-r10/final112/` locally and in the
same relative remote stage. Source, starts, clocks, sample size and thresholds
cannot change after launch. Controller `chesstk-odin-final-r10-a` has started
the primary suite on CPU0. Controller `chesstk-odin-final-r10-b` waits for
the last material-R8 development game to free CPU1, then runs its primary
lane. Each controller follows its40 primary games with16 original-Storm
guard games. Never pool development or guard into the primary confidence
interval. No promotion until all112 complete and both predeclared gates pass.

Newly supplied site rounds26–29 were screened independently:3 wins,1 draw,
777 positions, no exact-position overlap with the final holdout.15 diagnostic
roots were selected before consulting Odin answers, including the old300-ply
boundary in the long FuzzyBot draw. Full-history real-clock Odin probes and
2M-node same-root reference confirmations are in `lab/odin/new_games/`.
These are diagnostics only; the candidate weights were fixed before these
games arrived. No release-source changes are being made from these results.

The updates below retain earlier experiment context and are superseded by
the status above where they describe a queued or unstarted job.

**20:53 UTC continuation safeguard:** both final lanes are active. The first
two completed games (263 plies) pass individual replay/clock/resource evidence
checks. The full-sample gates are still pending. Local hidden finalizer PID16916
(`lab/odin/native_release/finalize_when_ready.py`) polls the existing authorized
SSH connection, downloads all four complete logs, runs the full promotion
validator in dry-run mode, and applies the exact ZIP only if every gate passes.
Its status is `lab/odin/native_release/odin-release-r10/finalizer-status.json`;
the report destination is `lab/odin/promotion/reports/final-r10/`. No site upload
is performed. If user instructions change, stop that PID or create the
`STOP-FINALIZATION` file in the R10 stage before changing release inputs.
Do not launch a duplicate finalizer. Connection details are process-local and
are never saved in the repository. The full new-game review is complete at
`docs/ODIN_NEW_GAMES_REVIEW.md`; it honestly records both recoveries and
remaining failures. R8 ultimately completed4W/3D/1L, zero faults; R7 was already
selected before that result and the release remains frozen.

Companion PID24560 (`keep_finalizer_awake.py`) holds a temporary Windows idle-
sleep request only while finalizer PID16916 exists, with a13-hour upper bound.
It does not hold the display on or modify persistent power settings. Explicit
user sleep/lid actions still take precedence. It releases its request on exit.

**Final-day data update:** round30 Team1 loss reviewed, completing the site
record9W/2D/4L in15. Allfive newly supplied rounds now total904 reconstructed
positions with no exact holdout overlap.40 Windows probes across20 selected
roots are complete. Odin's adaptive25.axb5 avoids the bad Team1 queen trade;
29.Kf2 remains unresolved. `chesstk-odin-queued-new-game-diagnostics` waits for
final lane a to finish all56 games, then uses its freed CPU0 for40 exact-source
Linux root probes under one-core/2GiB limits. It writes
`odin-release-r10/new-games-native-probes.jsonl` remotely and is a separate
diagnostic job, not a source change or replacement for the fixed strength gate.

**20:26 UTC update:** R6 completed2W/4D/2L with zero faults. R7 passed its
native gate (about35s imports) and won its first4 development games, covering
two complete color pairs; four remain. R8 passed its native gate and has
1W/2D in its first3 games; five remain. Both continue on their own VPS cores.
The cache and sort optimizations remain excluded: cached search took15.72s
against15.58s uncached on11 fixed-depth roots with identical nodes/scores/moves;
the sort microbenchmark saved only5.4% of sort time, with no demonstrated
whole-search gain.

Prepared `odin_submission/` differs from R7 only in naming/documentation and
total-domain guards in the two fifty-move helpers. Removing those guards gives
the identical helper AST; existing search callers already enforce their domain.
Linux stage `odin-release-r10`, ZIP SHA-256
`c7d8972e823eb821c016010445d4b02996daff954d870d63083c445850e21102`.
Its native gate, SEE/EP/warm-signature probe and3,857-state differential are
queued on CPU0 after `chesstk-odin-queued-positional-r7.service` ends, through
`chesstk-odin-release-validation-r10`. This job does not start final games.
The final80+32 plan is still not frozen or executed. Finalize selection only
after reviewing development results. The exact final source must pass its own
native evidence before the holdout. `ODIN_AGENT_EXPLAINER.md` documents the
original fitting and current engine behavior for a reviewer.

Current contract/rules were retrieved again successfully by HTTPS at20:24 UTC
and saved as `lab/odin/native_release/live-*-final.md`; the runtime, clocks,
600-ply rule, readable-source requirement and permission for offline
engine-labelled training remain as tested. Desktop Storm/v3 hashes were also
reverified unchanged. A partial failed UTF-8 documentation build was preserved
as `odin_submission-incomplete-20260905/`; it is never a package input.

## Native development decision

The supplied exact-history search foundation is operationally sound after
repairs, but lost badly to the genuinely minimal current-rules Storm control.
Fixed foundation r1 scored 0W/3D/1L; history-optimized r2 and compact/sparse r4
each scored 1W/2D/5L in their complete short-clock development samples.
These are rejected for strength. Their correctness fixes remain useful.

The next search lineage preserves Storm's fast position TT, PVS, LMR, null
pruning and cycle-as-draw search heuristic. This is deliberately a heuristic
search policy, not the exact full-history threefold predicates of the rejected
foundation. It retains current 600-ply draw rules, FEN absolute counters,
dynamic history capacity, legal root firewall, legal EP hashing and SEE,
all legal root moves, and guaranteed native-root compilation during import.

| Variant | Canonical source | Exact Linux ZIP SHA-256 | Status |
|---|---|---|---|
| Minimal control r1 | `storm_rules600_release_control/` | `35c6a33fed2e81acead145de53639ce516b1d24a6701a89a8c5fff81a582baf1` | Frozen control |
| Storm-plus r6 | `odin_storm_plus/` | `4b9edcf1d4b9fdba9387962abf8a706defffdcbc384a4428d1ffd6e591837299` | Complete2W/4D/2L, zero faults |
| Positional r7 | `odin_positional/` | `5a1f38d31bdc191514ed6474e5def9fb995eb7af367e2e9ff3aa0088e7048a03` | Complete6W/1D/1L, zero faults; selected lineage |
| Material r8 | `odin_material/` | `d454dda660a9dfacb07a44b9dee5069bbbe9a03aa42882da5143e17afe722edf` | Native gate then 8 games queued on CPU1 |

Each VPS CPU runs at most one active player from one match. Separate opponent
processes wait between requests. The source-only Linux ZIP is identical to
the tested extracted files. Each player gets one CPU, 2 GiB, single-thread
libraries and a 90-second import limit. Current development clocks are
60,000 ms +500 ms, four opening pairs, indices0–3 of `development.fen`.
These results cannot be pooled with the earlier30,000+100 development games.
The queues wait for the preceding CPU lane to finish before compiling.

## Local independent checks

- R6: legal/pinned SEE, legal EP identity, all-root retention, and no deferred
  native root specialization passed. Windows import was99.1s; only the Linux
  timing is release evidence.
- R7: 11,202 native feature/correction cases match independent python-chess
  geometry, including color mirrors. Raw laptop evaluation costs about495ns
  against12ns for PeSTO; this is not search NPS or a playing-strength claim.
- R8: 3,857 legal states and9,503 make/unmake edges pass, including exact
  accumulator reconstruction, EP, fifty-move boundaries and37 diagnostics.
  This lineage's fifty-claim helper requires a >=99 caller precondition;
  both search callers enforce it. The differential test explicitly follows
  that contract and does not assert exact threefold search.

## Offline evaluation experiments

`lab/odin/quiet_eval/` retains frozen selection/fit plans, source/reference
hashes, all labels and reports. 6,000 planned rows were processed by four
one-thread local SF19 workers. 5,668 passed the stable, exact-score, quiet-leaf
screen; deduplication leaves4,247 training and1,354 validation rows from
disjoint original opening families. No release holdout positions were used.

The original11 geometry features improve untouched validation MAE by only
1.20cp (1.21%). The subsequent24-feature experiment adds bishop pairs,
safe mobility, queen-dependent king pressure, advanced passers, seventh-rank
rooks and material corrections. Training-only family selection chooses ridge100;
its reused-validation MAE is97.24cp against99.47cp. R7 tests these weights.
R8 instead bakes six fitted material/pair features into the existing reversible
PeSTO accumulators, with only two bishop popcounts added at evaluation time.
Its reused-validation MAE is98.46cp. These reused validation figures are
exploratory and do not prove strength. Neither experiment includes any
Stockfish executable, labels, position answers or runtime training in its ZIP.

## Continuation

Retrieve final r6 logs, then r7/r8 native gates and development games. Local
critical-root probes for r7/r8 are running on CPUs5/6 and write into
`lab/odin/development_review/`. Queue names and stage labels match the table;
connection details stay outside the repository. The existing authorized SSH
destination is recoverable from chess-specific shell history, without printing
it. If the persisted key is unavailable, check the Windows ssh-agent service.

Select a genuinely promising candidate, finish source cleanup and final native
correctness checks, then build a new exact Linux release. Freeze the80+32 plan
with `lab/odin/native_release/freeze_plan.py` before any final game. Run two
lanes with `run_final_lane.py`; inspect all evidence using the release validator.
Primary promotion requires the paired95% score interval lower bound above0.5;
the original-Storm guard requires raw score above0.5. All112 games and zero
operational faults are mandatory. No optional stopping or altered sample size.
`lab/odin/promotion/promote.py` dry-run and `--apply` then copy the exact tested
archive to Desktop `agent.zip`, preserving the known Storm/v3 backups. Do not
upload the website. Update the implementation handoff when finished.
