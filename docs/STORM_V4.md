# Storm v4 development and validation

**5 September follow-up:** Storm's first ten site games and all native v3
matches are now reviewed in `ODIN_REVIEW.md`. The updated continuation prompt
assigns the successor **Odin**. The live referee now draws at 600 total plies,
including the opening; references below to 300-ply material adjudication
describe the historical Storm build/tests. Storm source and release bytes
were preserved; the Odin implementation brief specifies the required fixes.

Started 4 September 2026 under the user's explicit authorization to reopen the
engine design. **Storm v4 was promoted on 5 September after its fixed native
holdout passed.** At the user's request on 5 September, Desktop `agent.zip`
became the official Storm v4 upload file, byte-identical to Desktop
`Storm-v4.zip` and `dist/agent-storm-v4-linux-x86.zip`. The former Desktop
`agent.zip` was renamed to `v3-agent.zip`, preserving the exact v3 baseline.
All desktop archive identities were verified after the rename/copy.
No platform submission was performed here; the user handles that step.
See `STORM_CONTINUATION_PROMPT.md` for the next development session.

## Design

Storm uses our verified v3 board representation, move generation, published
PeSTO tables and referee integration as its foundation. Its new search design
combines history-aware late-move reductions with full-depth verification,
positive/negative history learning, less destructive sacrifice pruning,
static-evaluation-gated null moves, and a new iterative-deepening controller.
An exact incremental PeSTO accumulator removes repeated whole-board evaluation
scans. A readable LLVM bit-scan intrinsic compiles through the preinstalled
Numba stack; no native binary or external engine is shipped.

Time is allocated using material phase and actual elapsed game plies. Changing
best moves, score deterioration and failed aspiration searches increase the
search allowance. Repeated stable decisions reduce it. Forced legal replies
return immediately. The compiled search checks a real monotonic wall deadline
every 1,024 nodes, including depth one and quiescence, retaining the latest
completed iteration. The agent emits compact depth/node/score/time telemetry.

These are original extensions to our engine. They are not a claim to a new
chess-search algorithm, nor evidence about private rival implementations.

Three inherited comments in the frozen source still describe v3 behavior:
the `search_nb.py` module summary says "No LMR", its Python depth-one note
calls that iteration unabortable, and a `core_nb.py` iterative-deepening note
refers to an old minimum allowance. The executable paths and regression tests
implement the behavior described above. Comments are left unchanged during
the fixed-archive match.

## Live contract

Re-fetched directly on 4 September: Python 3.12, fixed stack versions, one AMD
EPYC 9V74 core at 2.60 GHz, 2 GiB, 120 s + 0.5 s, 90 s initialization, 300-ply
material adjudication, automatic draw claims. Processes are suspended while
their opponent thinks. Sources: [contract](https://aichessathon.com/docs/agent-contract.md),
[rules](https://aichessathon.com/docs/rules.md).

## Structural and efficiency evidence

- All 15 games and 1,712 plies replayed; see `STORM_GAME_FORENSICS.md`.
- Six standard Numba perft positions, search/draw/mate/promotion regressions.
- 600 random-game positions plus every special move at test roots: incremental
  PeSTO equals the independent scanning evaluator; all undo states exact.
- Selectivity tests: reduced false cutoff must receive full-depth verification,
  history can unlearn bad moves, actual mates/promotions, deadline abort restores
  the board even at depth one.
- 16 clock policy tests, including randomized budget bounds and simulated games.
- Six bit-scan tests, including all singleton/two-bit boards and 12,004 samples.
- The initial Storm build before the bit-scan improvement searched 32 identical
  recorded-game positions to nominal depth five in 1.624 s / 425,503 nodes;
  v3 used 7.661 s / 727,795 nodes. Different selective trees make this a local
  efficiency screen, not an Elo estimate. 29/32 chosen moves agreed.
- The bit-scan revision preserved every move, score and node count on those
  same 32 roots. Time fell from 1.624 to 1.484 s, a 9.44% throughput improvement
  in the sequential Windows comparison. This supports the specific codegen
  change; it is not a claim of a twofold full-engine speedup.

The subsequent **native Linux comparison supersedes the Windows timings for
runtime claims**. On the same 32 roots at nominal depth five, with both exact
archives and cleared TT/history/killers per root:

| Native diagnostic | Storm v4 r2 | v3 |
|---|---:|---:|
| Nodes | 425,503 | 727,795 |
| Search seconds | 0.461744 | 0.739777 |
| Cold warmup seconds | 27.907 | 24.069 |

Storm finished this workload **1.602 times faster**, with **41.535% fewer nodes**.
Its aggregate node throughput was **6.33% lower**, so the native result does
not establish a faster per-node evaluator/core. Different node mixes also
prevent treating that throughput figure as a pure evaluation microbenchmark.
All moves, scores and node counts matched each archive's Windows reference;
Storm and v3 selected the same move on 29 of 32 roots.

This was one sequential sample per archive on a free signer core, after that
core's holdout lane had exited. It omitted live time allocation/deadlines and
used historical diagnostic roots, so it is efficiency evidence, not a second
strength test. The larger Windows speedup must not be projected onto Linux.
Full record: `lab/storm/native-efficiency-r2-v3.json`.

## Native release: Storm v4, revision r2

Archive: `dist/agent-storm-v4-linux-x86.zip`. It is byte-identical to the frozen
`dist/storm-r2-linux-x86.zip`; the Windows delivery step only copied those
Linux-built bytes.

SHA-256: `15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c`.

Packed on Linux x86-64 Python 3.12 with NumPy 2.5.2, Numba 0.67.0 and chess
1.11.2. Every member's hash matches the input snapshot; source only, root
`agent.py`, Unix ZIP metadata. Tests ran on a clean extraction of final bytes.
Native structural warmup: 28.810 s. Separate official-runner cold readiness:
28.671 s, below our 55 s target and the live 90 s limit. Structural, accumulator,
deadline and protocol probes passed. Tactical first calls did not compile again.

The native gate pins one core, applies a 100% CPU quota and 2 GiB memory cap,
disables swap and internet address families, and uses read-only extracted
submission files. This VPS has no full read-only container root or aggregate
256 MiB tmpfs. Its CPU is not the site's EPYC; results are native Linux evidence,
not identical hardware evidence.

## Match gate declared before play

First run a short-clock development screen on paired opening indices 140–143.
If operationally clean and not clearly losing, freeze candidate bytes and run
20 fresh opening pairs at 120 s + 0.5 s on indices 160–179. No candidate edits
during that holdout. Both colours per opening, unchanged official referee,
fresh processes and source snapshots. Report all failures and exact hashes.
These are previously unused slices of our local synthetic opening corpus:
8–12 plies of generated play, at least 28 pieces, and a small initial PeSTO
imbalance. They are not the organiser's unpublished opening set, and a match
against v3 does not establish a leaderboard rank or rival-technology claim.

Promotion requires all 20 pairs completed, zero candidate operational failures,
and a paired 95% bootstrap lower score bound above 50% against the signed v3.
An inconclusive score is not superiority. Development screens, speed tests and
the observed site games do not count as that final match.

Development screen completed: **8 wins, no draws or losses**, all checkmates,
against signed v3 at 10 s + 0.1 s on indices 140–143. Neither side had any
operational failure. Peak observed cgroup memory: Storm 414 MiB, v3 396 MiB.
All source snapshots stayed unchanged. This short-clock result is not included
in the separate full-clock confidence interval.

The first half of the full-clock holdout began on CPU 1 after the first two
screen pairs were clean, while the remaining screen finished on CPU 0. Once
the screen finished, the other ten holdout pairs began on CPU 0. The candidate
bytes were fixed before either holdout lane. Each pair alternates agents on
one pinned core with its own per-agent resource envelope. Four resident agents
fit comfortably within the measured host memory; each active search has its
core to itself. The two lanes have distinct run IDs and opening slices.

## Completed full-clock result

**PASS: 31 wins, four draws, five losses; 33/40 points = 82.5% score.** The
outright win rate is 77.5%. The paired 95% bootstrap score interval is
**71.25–92.5%**, from 20,000 opening-pair resamples with seed 20260904. The
relative logistic Elo estimate is +269, interval +158 to +436, for this matchup
and corpus only; it is not a predicted platform rating.

All 20 predeclared colour pairs on indices 160–179 finished using unchanged
archive bytes. Both engines had **zero operational failures**; every win was
by checkmate. All 40 games and 5,028 plies replayed legally, with matching
requests, FENs, clocks and outcomes. The independent evidence audit verified
80 fresh agent services, distinct CPU assignments, package/source/ZIP hashes,
resource envelopes, clean extraction/cleanup and both final run summaries.

| Full-clock measurement | Storm v4 | v3 |
|---|---:|---:|
| Mean time remaining | 15.758 s | 23.499 s |
| Mean thinking, including increment-funded time | 135.738 s | 127.848 s |
| First 20 decisions, mean total | 65.021 s | 72.550 s |
| First-20 total, standard deviation | 8.503 s | 2.355 s |
| Decisions 21–40, mean time per decision | 2.803 s | 1.909 s |
| Decisions 61 onward, mean time per decision | 0.439 s | 0.614 s |
| Slowest native import | 30.079 s | 26.026 s |
| Peak observed native cgroup memory | 413.820 MiB | 395.746 MiB |

First-20 totals include the 39 games long enough to supply 20 decisions to
both engines. Phase/decision-bin averages compare their observed moves, not
identical counterfactual positions. More variable time allocation and less
remaining time are observations, not separate proof of which feature caused
the match gain.

Evidence: `lab/storm/holdout-r2-audit.json`, `holdout-r2-summary.json`, both
`holdout-r2-lane-*.jsonl` logs, and `docs/STORM_MATCH_EVIDENCE_REVIEW.md`.
Delivery metadata: `dist/agent-storm-v4-linux-x86.release.json`.

Final analysis must include only the two full-clock holdout logs, not the
short-clock screen. The paired statistics helper does not itself validate
time-control metadata. Both completed run summaries, identical clock settings,
archive hashes and resource-envelope records must therefore be checked as well.
`S4 t` measures the native search only and `S4 b` is the final soft target;
forced and panic moves may have no telemetry. Report total thinking and clock
remaining from the official referee's per-request timings.

`lab/storm/export_games.py` exports replay-verified PGNs with `%clk`/`%emt`
annotations and a per-move CSV from the original match logs. All 40 full-clock
games are in `lab/storm/Storm-v4-vs-v3-games.pgn`, with a companion CSV. The
screen remains separate in `lab/storm/screen-r2-games.pgn`.

## Supplementary actual-site opening check

Two selected historical site starts, each played with both colours on Windows
at 120 s + 0.5 s, finished **one Storm win and three draws**. Neither side had
an operational failure or a readiness override. This small, selected sample
is separate from the native holdout; its more modest result matters when
interpreting how far the synthetic-opening gain might transfer.

Storm averaged 14.132 s remaining versus v3's 22.065 s in these four games.
One game lasted 293 plies and ended in a fifty-move draw with rook and bishop
against rook. A different draw featured repeated queen checks despite Storm's
two extra pawns and its final search scores of zero. Neither material surplus
alone establishes that the engine discarded a win.

The Windows environment was variable: Storm's slowest import was 85.531 s,
still below the live 90 s but far above native measurements. The local runner's
RSS samples cover its launcher, so they are not engine memory measurements.
Full evidence and clocked PGNs: `docs/STORM_SITE_STRESS.md`.

## Known remaining weaknesses and optional evaluator

On the historical R12 diagnostics, r2 still chose 16.Nxd6 and 24.Rh3 rather
than the site's earlier review preferences Nxc5 and Rb3 at both 3 s and 9 s.
R4's 13...Qd8 preference also survives. More nominal depth has not solved these
positions. `lab/storm/diagnostic_comparison_summary.json` records exact source
hashes, actual time, scores and completed depths. V3 sometimes exceeded its
requested diagnostic time; the report preserves those overruns.

The first native holdout loss exposed rook-ending conversion and late clock
allocation weaknesses: Storm gained a pawn and advanced a blocked a-pawn,
then lost a two-wing pawn race and its rook to a skewer. No runtime anomaly
was found, and the evidence does not establish a single first blunder or a
proven alternative win. `docs/STORM_R2_LOSS_165.md` retains all 205 plies with
clock/material/search traces. The engine stayed fixed throughout the holdout.

An isolated `dist/storm-eval-r3` experiment adds small tapered mobility,
king-danger/shelter, bishop-pair, passed-pawn/king-distance and bare-king
conversion terms. It has not joined the release. Its initial 32-position
depth-five screen took 65% longer than r2, so evaluation richness has a real
depth cost. It also did not recover the two R12 preferences. Any improvement
must come from games, not feature count or plausible explanations.

That experiment's local short-clock screen stopped at game five after an
initialization loss: 92.817 s against the 90 s allowance. Its raw record was
three wins and two losses, including that failure; only two colour pairs had
completed. It is not promoted and none of its evaluator code is in the r2
release candidate. See `docs/STORM_EVAL_R3_EXPERIMENT.md` for the retained work.
