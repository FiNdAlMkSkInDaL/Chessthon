# Odin v6 — overnight handoff

**Completed and promoted on 6 September:** all 112 games audited PASS,
30W/69D/13L (57.59%), paired 95% interval 52.23–62.95%, zero faults.
the signer archive (not in git) is now the tested v6 archive. See
[ODIN_V6_RELEASE_REPORT.md](ODIN_V6_RELEASE_REPORT.md). The instructions and
launch status below are retained as historical provenance. The automatic
audit import error was repaired by setting the pinned harness import path;
read `review-audit.json` / `local-review-audit.json`, not the original failed
`COMPLETE.json` alone.

Status at 2026-09-05 23:31 UTC (00:31 London, 6 September): the exact Linux
archive passed its native gate, and the 112-game overnight test is running
on the VPS. Both lanes and the persistent controller were verified active.
No site upload or promotion has occurred.

## What to do tomorrow

Continue this task by reading this file first. Use the established signer
connection; do not discover a new login or put credentials in the workspace.
Remote working directory:
`$HOME/chess-sign-odin-20260905/odin-v6-architecture-r1`.
Remote Python: `$HOME/chess-tk/.venv/bin/python`.

1. Read `overnight112/progress.json`, `COMPLETE.json` and `final-audit.json`.
   Inspect the services `chesstk-odin-v6-112-controller`,
   `chesstk-odin-v6-112-a` and `chesstk-odin-v6-112-b` if incomplete or failed.
   Do not launch duplicate matches. `Linger=yes` was verified: these jobs
   survive SSH disconnection, laptop sleep and closing Codex.
2. Download the complete logs, plan, audit and completion record into the
   local `lab/odin/native_release/odin-v6-architecture-r1/overnight112/`.
   The local frozen plan is already saved as `overnight-plan.json` one level up.
3. Require exactly 112 games / 56 complete color-reversed opening pairs,
   correct candidate/baseline/archive/helper identities, legal PGN replay,
   current referee outcomes, and zero crashes, flags, illegal moves, init
   failures, envelope violations or extraction mutations. The existing
   validator performs these checks; inspect every reported error.
4. Report wins/draws/losses, points percentage and the paired 95% confidence
   interval. The frozen promotion criterion is its lower bound strictly
   above 50%. Do not relax it after seeing the result. Operational faults
   stop the affected lane after its current pair; partial data do not pass.
5. Review initialization, clock use, depth and endgame/draw telemetry too.
   The 18 short screening games below are development data; never add them
   to the 112-game score or confidence interval.
6. If all gates pass, the user has already authorized a final upload-ready
   the signer archive (not in git) when Odin improves. Preserve `Odin-v5.zip`, verify
   current `agent.zip` is still the v5 hash below, and replace it with the
   **exact already-tested Linux ZIP**, not a fresh Windows archive. Preserve
   an `Odin-v6.zip` copy and write a release report. If anything changed on
   the archive location meanwhile, investigate instead of overwriting it blindly.
   Do not upload to the site without the user's instruction.
7. If the evidence does not pass, explain the specific result and keep v5
   released. Do not substitute the marginal parameter variants or silently
   restart/tune on this now-used holdout.

To independently repeat the completed log audit on the signer, from the
remote stage directory:

```sh
PYTHONPATH="$PWD/lab/odin/official-harness-91f70e54:$PWD" \
"$HOME/chess-tk/.venv/bin/python" -B -m lab.odin.release.validate_match \
  --plan overnight112/plan.json --suite primary \
  --out overnight112/review-audit.json \
  overnight112/primary-a.jsonl overnight112/primary-b.jsonl
```

## Frozen identities

| Item | SHA-256 |
|---|---|
| Odin v6 candidate ZIP | `cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647` |
| Released Odin v5 / the signer archive (not in git) | `c7d8972e823eb821c016010445d4b02996daff954d870d63083c445850e21102` |
| Overnight plan | `929bb3249d938ebf0435668f206be00e220e55a4e6e5b47056c90ad7c891debe` |
| Frozen 56-opening FEN file | `a2a8f62cadf481adacbb101f87c34a6e7c7125569f49d1bfe672e2bbfe6fea67` |

Candidate local source is `odin_v6/`; archive and native gate are in
`lab/odin/native_release/odin-v6-architecture-r1/`. An identical candidate
copy is outside git as `Odin-v6-candidate.zip`. the signer archive (not in git) is still v5.
The final source differs from the measured `odin_fast_checks/` only in its
version comment; all 12 module ASTs were checked identical before packing.
`lab/odin/fast/architecture-manifest.json` binds the full member hashes.

The baseline archive is the original released R10 archive on the signer at
`../odin-release-r10/candidate-linux-x86.zip`. Do not reactivate old R10
finalizers or remove its `STOP-FINALIZATION` marker. That old full test was
stopped by the user after 16 games; this is a new, separate test.

## What v6 changes

This is a throughput architecture change preserving Odin v5 search/evaluation
semantics at equal node budgets:

- Test move legality using pins and resulting occupancy without making and
  undoing every pseudo-legal move. King moves, EP and castling have exact tests.
- Generate captures and promotions directly for quiescence; preserve order.
- Compute geometric ray masks at import and locate the first blocker with
  compiler bit scans, replacing square-by-square slider walks.
- Detect checking moves and pinned pieces without redundant state updates.
- Fuse the existing original 24-feature evaluation into equivalent weighted
  accumulators. The fitted weights and search parameters remain v5's.

There is no shipped network, third-party engine code, published network,
magic lookup table or runtime engine-answer database. New bit-scan code uses
the already installed Numba/LLVM stack; tables are computed board geometry.

## Completed evidence

- Native mixed-position benchmark: 40 positions, one million nodes each,
  alternating baseline/candidate order on the same CPU. All chosen moves,
  scores, depths and node counts matched. Total search time 51.552s to
  32.805s: **1.5714x throughput / 36.4% less time for the same search**.
  See `lab/odin/fast/checks-mixed-benchmark-linux-r2.json` and streamed JSONL.
- Differential legality: 9,221 positions / 218,670 legal moves, including
  20 EP moves, 505 castles, 720 promotions and 487 checked positions;
  exact move order against the original trial filter, exact legal/noisy
  move sets and all gives-check flags against python-chess; state unchanged.
  Six standard depth-four perft fixtures passed. See `fast-checks-test.json`.
- Ray proof: 1,119,744 exhaustive rook/bishop occupancy subsets including
  edge blockers, 20,000 random full-board cases, and MSB bit tests.
  See `ray-mask-test.json`.
- Complete short equal-time screen: **10W / 8D / 0L, 77.78% points**, 18 games
  on nine development pairs, equal 100ms search-time allowance per move.
  All 2,098 plies replay-audited; reset isolation and native calls verified.
  This is NOT the full competition clock or an unbiased strength estimate.
  See `checks-clock-screen.jsonl` and `checks-clock-audit.json`.
- Exact Linux ZIP native gate PASS: cold imports **33.573s / 34.158s**;
  six perft probes, twelve deadline probes, six current-rules/history cases,
  official-runner protocol checks, read-only source and envelope checks.

The first mixed benchmark completed comparisons but failed at report
aggregation due to a harness variable-shadowing bug. R2 repaired that bug
and repeats the complete measurement with streamed rows. Only R2 is the
completed benchmark evidence; do not hide or reinterpret the earlier errors.

## Why this candidate, not the earlier variants

The 14-member initial generation played 252 games. Four finalists then
played 192 deeper games: IIR off 52.083%, SEE ordering 50%, IIR delayed
48.958%, combined SEE/IIR 48.958%. A fifteenth continuation-history variant
scored 47.22% in its 18-game screen. These did not establish a leap.
The user explicitly requested continued search for a larger change.

A subsequent original 12-configuration neural trial overfit: every setting
selected its first training epoch on the opening-family inner split. Its
best reused-validation MAE was 96.81cp against 97.25cp for Odin, insufficient
to justify integration. Training code, plan, weights and results remain
offline in `lab/odin/fast/network-training/` for honest provenance.

The geometric/search-throughput rewrite above then produced the larger
measured gain. Do not claim its 57.1% throughput gain is a 57.1% Elo or win-rate
gain. The final 112-game holdout is what determines the full-clock result.

## Overnight conditions and practical limits

56 fresh, frozen, color-paired openings; both contestants use 120s+0.5s wall
clock, 90s init, 600 absolute plies then draw, normal automatic outcomes
first. Untouched official starter commit:
`91f70e54be07e1bf56311962044a08b822c3af50`.
Runtime Python3.12.3, chess1.11.2, numpy2.5.2, numba0.67.0, llvmlite0.49.0.
Each fresh agent receives one CPU, 100% quota, 2GiB memory, no swap,
AF_UNIX-only network creation, task/file-size limits and read-only extraction.
Lane a uses CPU0/even opening indices; lane b CPU1/odd indices.

The VPS is EPYC-Genoa, not the competition's exact EPYC9V74. The laboratory
does not reproduce a fully read-only root/aggregate temporary-disk quota,
and its nonmoving engine waits on stdin rather than physical suspension.
Do not describe this as identical competition hardware. Relative matched
tests and the pinned referee are the evidence available.
Previously paused collectors remain as found; do not restore them mid-match.
The durable controller writes the final audit when both lanes finish and
never promotes automatically. No new assistant thread or subagent was used.
