# Continue Storm chess-engine development

Work in `the repository root`.
This is a continuation of completed Storm v4 work, not a request to restart
the old v3 project. Read this handoff, inspect the current files, and then
continue implementation and measured improvement autonomously. Do not stop
after a plan or repeat completed matches without a concrete reason.

## Objective and authority

I want a substantially stronger successor to Storm v4 for AI Chessathon,
capable of competing with the leading bots. I have authorized reopening the
old feature exclusions and choosing sophisticated approaches within the
competition rules. Optimize actual playing strength and decision quality;
reliability is a required gate, not a substitute for strength. Better timing
matters, but finishing with an empty clock is not itself the objective.

Read `AGENTS.md` and `ENGINEERING.md`, especially the Storm reopening notice
at the top. The earlier blanket bans on exploring LMR, evaluation changes,
and other engine improvements were superseded by my explicit authorization.
Follow the live rules where old documents disagree. Re-fetch:

- https://aichessathon.com/docs/agent-contract.md
- https://aichessathon.com/docs/rules.md
- https://aichessathon.com/leaderboard when making current leaderboard claims.

I handle uploading to the site. Prepare and validate the next candidate;
preserve the current official release while doing experiments. There is no
need to ask again for permission to inspect, code, test or conduct ordinary
authorized development. Use parallel agents for independent useful work.

## Exact current state, 5 September 2026

The previous task is complete. All native matches, local supplementary
matches and benchmarks finished. No engine or benchmark jobs were left
running, and no new scheduled work was created. Recheck resource availability
before launching anything; old session IDs are not active jobs to resume.
The workspace had no Git repository at handoff.

The desktop files were changed at my request, with hashes checked afterward:

| Archive filename | Contents | SHA-256 |
|---|---|---|
| `agent.zip` | Official Storm v4, revision r2 | `15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c` |
| `Storm-v4.zip` | Same exact Storm bytes | `15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c` |
| `v3-agent.zip` | Previous exact v3 | `3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408` |
| `agent.pre-v3-FBB10AD7475.zip` | v1 that played the original 15 site rounds | `fbb10ad7475b5bb1ad50c21e38d121b917d09bce0ce8ce36bc8d6c02de8d8110` |

Those copies were kept outside git. The agent has not
uploaded Storm or verified my subsequent upload; do not infer site status
from the local filename.

The release source is **`storm/`**, whose 12 root Python files matched the
frozen ZIP at handoff. The archive is 33,227 bytes, Linux-built, source only,
with `agent.py` at its root. Identical retained copies:
`dist/agent-storm-v4-linux-x86.zip` and `dist/storm-r2-linux-x86.zip`.
Metadata: `dist/agent-storm-v4-linux-x86.release.json` and
`dist/storm-r2-linux-x86.manifest.json`.

`dist/agent-v3-linux-x86.zip` is v3. **`dist/agent.zip` remains v1.** Root-level
engine files are older; `make zip` does not package Storm. Do not edit the
wrong engine or accidentally replace the official archive with a root build.
Preserve release evidence and create a distinct candidate snapshot for new
work; new release archives must be packed and tested on native Linux x86-64.

## Read these records before choosing changes

1. `docs/STORM_V4.md`: complete design, release gate, results and limitations.
2. `docs/STORM_MATCH_EVIDENCE_REVIEW.md`: independent provenance and statistical
   audit, plus the mismatch between synthetic and actual site openings.
3. `docs/STORM_GAME_FORENSICS.md`: all 15 v1 site games and public leader data.
4. `docs/STORM_R2_LOSS_165.md`: retained rook-ending loss and full clock trace.
5. `docs/STORM_SITE_STRESS.md`: four completed actual-site opening games.
6. `docs/STORM_EVAL_R3_EXPERIMENT.md`: isolated, unpromoted evaluator experiment.

## What Storm already implements

It retains our tested v3 board representation, ray move generator, published
PeSTO tables and referee integration. New work includes history-aware LMR
with full-depth verification of reduced alpha-improvers, bounded positive
and negative history learning, improved capture/promotion ordering, less
destructive sacrifice pruning, static-evaluation-gated null moves and guards
against consecutive nulls. Material-adjudication mode disables IIR/LMR.

PeSTO middlegame/endgame/phase sums are maintained exactly on make/unmake,
with an independent scanning reference evaluator. A readable LLVM bit-scan
intrinsic uses installed Numba/llvmlite; no native binary is shipped.

`storm_clock.py` uses material phase, observed game age, completed-best-move
stability, score deterioration, aspiration failures and observed depth cost.
Planning horizon ranges from 32 to 8 decisions. There is a 400 ms hard
margin, 1,500 ms soft reserve and increment-aware planning. Soft effort can
vary from 0.55 to 2.4 times base; a soft target is not a hard deadline.
Forced legal replies return immediately. Hard budgets do not borrow future
increment. Native search checks a monotonic deadline every 1,024 nodes,
including depth one and quiescence, and preserves a legal completed fallback.
Native failure does not receive a fresh full budget for Python fallback.

The entrypoint emits `S4` phase/depth/nodes/score/time/budget telemetry.
`S4 t` is search-only time and `S4 b` is the final soft target. Forced/panic
branches can omit telemetry. Use referee request timings for whole-clock
claims; v3 has no equivalent depth telemetry.

Three frozen source comments still describe old behavior: search_nb says
"No LMR" and calls depth one unabortable, and core_nb has an old minimum-time
note. Inspect executable paths and tests. Do not alter release bytes merely
to correct comments; corrections can accompany a distinct new candidate.

## Completed evidence: do not reinterpret or pool it

The fixed native holdout was 20 fresh colour pairs, 40 games, synthetic
opening indices 160–179, 120 s + 0.5 s. Storm beat exact v3 **31 wins,
4 draws, 5 losses**, scoring **82.5%** (77.5% outright wins). Paired 95%
bootstrap score interval: **71.25–92.5%**, 20,000 resamples, seed 20260904.
Zero operational failures on either side. All 40 games / 5,028 plies replayed
legally and matched logged FENs and outcomes; all 36 decisive games were mates.
This demonstrates improvement over v3 on that corpus, not a leaderboard rank.

Final evidence: `lab/storm/holdout-r2-audit.json`,
`lab/storm/holdout-r2-summary.json`, `lab/storm/holdout-r2-lane-a.jsonl`,
`lab/storm/holdout-r2-lane-b.jsonl`. Clocked games and per-move data are in
`lab/storm/Storm-v4-vs-v3-games.pgn` and its companion CSV.

Mean remaining time was 15.758 s for Storm versus 23.499 s for v3.
Decisions 21–40 averaged 2.803 versus 1.909 s. Native slowest import was
30.079 versus 26.026 s, peak cgroup memory 413.820 versus 395.746 MiB.
Both native lanes had separate cores; each playing process had one core,
100% quota, 2 GiB cap, no swap, restricted networking and single-thread env.
The VPS lacks a full read-only container root and aggregate 256 MiB tmpfs,
and its CPU differs from the site's. These are recorded limitations.

The preceding 10 s + 0.1 s screen was 8–0 on indices 140–143. Keep it separate.
Two selected actual-site starts with both colours produced **one win and
three draws** at 120 s + 0.5 s on Windows, with no operational failures.
This small selected sample is also separate. Storm's slowest Windows import
there was 85.531 s; launcher RSS is not engine memory. Never claim these
four games reproduce the native holdout's margin.

The synthetic corpus is underdeveloped and uncastled: holdout starts averaged
1.4 minor pieces off the back rank, none castled, seven in check. The 14 unique
actual site starts averaged 4.21 developed minors, four castled positions,
none in check. Better coverage is a major next measurement priority.

Native fixed-depth diagnostic, 32 historical roots, exact archives, cleared
TT/history/killers: Storm 425,503 nodes / 0.461744 s; v3 727,795 / 0.739777 s.
That is **1.602 times faster total workload, with 41.535% fewer nodes**.
Storm's aggregate raw node throughput was 6.33% lower. Different node mixes
prevent pure evaluator-speed claims. This one sequential nominal-depth sample
is not an Elo test. Large early Windows speedups do not transfer to Linux.
Record: `lab/storm/native-efficiency-r2-v3.json`.

Public leader timing did show selective allocation, but its latest three
sampled games ended with an average 44.583 s remaining. This does not expose
private search algorithms and does not support spending every last second.
The old v1 15-game record was 8 wins, 2 draws, 5 losses; all losses were mates.

## Known weaknesses and unfinished research

- Historical R12: r2 still chose 16.Nxd6 and 24.Rh3 rather than the earlier
  site-review preferences Nxc5 and Rb3, at both 3 s and 9 s. R4's 13...Qd8
  preference persists. Site-review preferences are diagnostic leads, not
  certified ground truth. More nominal depth alone did not fix them.
- Opening 165, Storm Black: gained a pawn, blocked its own advanced a-pawn
  with its rook, entered a two-wing pawn race and lost a rook to a skewer.
  Final reserve was about 4.232 s. Own evaluation stayed positive well before
  deteriorating; this is a conversion/evaluation/search/time diagnostic, not
  proof of an objectively won position or the first losing move.
- One supplementary game reached 293 plies and a fifty-move draw with rook
  and bishop against rook. Another had two extra pawns but perpetual queen
  checks and zero search scores. Material surplus does not prove a missed win.

The isolated experiment in `dist/storm-eval-r3/` and
`dist/storm-eval-r3-experimental-windows.zip` is **not Storm v4**, not native
validated, and not promoted. It adds tapered mobility, king danger/shelter,
bishop pair, passed-pawn/king-distance and bare-king conversion terms.
Symmetry and make/unmake checks found and fixed two errors, but its Windows
depth-five workload was about 65% slower, and it did not solve the two R12
diagnostics. The short-clock match stopped at game five with a 92.817 s cold
init loss against the 90 s limit: raw +3=0−2, only two complete pairs. This is
a Windows failure, not evidence of a Linux failure. Reuse ideas only after
testing their cost and playing strength; do not simply merge the whole bundle.

## Tools, runtime and next validation

Installed local Python 3.12:
`python`.
The default Windows Python may be 3.14; do not use it as the runtime of record.
Last fetched live contract: Python 3.12, NumPy 2.5.2, Numba 0.67.0,
chess 1.11.2, llvmlite 0.49 dependency; 90 s init, 120 s + 0.5 s, one core,
2 GiB, no GPU/network, suspension during the opponent's turn, automatic draw
claims and 300 played plies to material adjudication. Re-verify mutable rules.
Never edit `harness/`, ship third-party engine code, or put credentials in files.

Native signing and matches already worked; do not assume the signer is
unavailable from old docs. Existing private connection details were resolved
locally from established chess-related SSH history, never saved in the repo.
Use only the known configured destination; do not guess accounts/hosts or
print credentials. Last remote work directory was
`$HOME/chess-sign-storm-r2-20260904`; Python was
`$HOME/chess-tk/.venv/bin/python`. These contain reproduction assets, not an
unfinished run. Check services, cores, memory and unrelated workloads first.

Useful existing tools:

- `lab/storm/gates.py`: native warmup, perft, search contract, exact accumulator,
  real deadlines and entrypoint probes; supports `STORM_SOURCE`.
- `lab/storm/test_selectivity.py`: pruning/history/deadline tests and optional
  fixed-depth benchmark; supports `--engine`.
- `lab/storm/test_clock.py`, `test_bitops.py`, `test_accumulators.py`: regression
  checks. Several directly import/default to `storm/`; ensure candidate code,
  not the old release, is under test when using a separate directory.
- `lab/storm/linux_sign.sh`: pack on Linux and test final extracted bytes;
  expects a fresh staging directory and flat Python source members.
- `lab/storm/linux_match.py`: immutable-archive matches with official referee,
  per-game services, logs and envelopes. Inspect its CLI before running.
- `lab/paired_match_stats.py`: paired score statistics, not a complete evidence
  auditor. It does not independently validate time-control/run metadata.
- `lab/storm/validate_holdout.py`: deliberately hardcoded to the **old r2-v3
  gate**, their hashes and indices 160–179. Keep it reproducible; a future
  candidate needs a new declared plan and corresponding evidence validation.
- `lab/storm/diagnostic_compare.py`, `inspect_game.py`, `export_games.py`,
  `summarize_match.py`, `report_site_stress.py`: diagnostics and replay exports.
  The clock summarizer assumes successful legal moves when crediting increment;
  handle any future failed requests explicitly rather than copying its averages.

Start by verifying release identities and reading the retained weaknesses.
Choose a small number of high-value hypotheses and divide independent analysis
and implementation work. Prioritize generalization to developed/castled site
starts and demonstrable conversion or decision-quality improvements. Define
tests and ablations that can distinguish useful changes from plausible stories.
Observed site games and the old holdout are now development evidence, not fresh
unseen validation. Predeclare a fresh, sufficiently broad paired full-clock
test against **Storm v4 r2**, freeze candidate bytes during it, retain failures,
and separate diagnostic/short-clock/native samples. Protect correctness,
init time, memory and deadlines while pursuing real strength gains. Deliver a
Linux-built candidate with exact hashes, reproducible evidence, limitations
and a clear promotion recommendation. Do not upload to the platform for me.
