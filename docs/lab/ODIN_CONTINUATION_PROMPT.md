# Build Odin, the successor to Storm

Work in `the repository root`.

We have completed Storm v4 and an expert review of its first ten platform
games, the 40 native Storm-v3 games and supplementary matches. Your task is
to **implement and validate the next iteration, Odin**. Do not start another
generic architecture debate or stop after a plan. Use the completed evidence
to build the concrete improvements below, and use parallel agents for useful
independent work.

## Read before implementation

Read `AGENTS.md`, then the current notices at the top of `ENGINEERING.md`.
My earlier authorization reopened the old feature exclusions; those historical
bans do not veto strength improvements within the live competition rules.
Read these documents in order:

1. `docs/ODIN_REVIEW.md` — final findings, strongest reference checks and limits.
2. `docs/ODIN_BUILD_BRIEF.md` — exact implementation sequence and acceptance gates.
3. `docs/ODIN_CODE_REVIEW.md` — affected functions, reproduced defects and probes.
4. `docs/ODIN_SITE_REVIEW.md` and `docs/ODIN_HOLDOUT_REVIEW.md` — every game,
   clocks, telemetry, sequences and positive regression controls.
5. `docs/STORM_V4.md` — the frozen baseline's design and historical validation.

The definitive development suite is `lab/odin/odin-diagnostics.jsonl`:
37 history-complete game roots plus two exact legal-exchange fixtures.
The site audit also retains 44 selected roots and all 572 Storm decisions in
`lab/odin/site_review.json`. These known cases are diagnostics, not your final
unseen test set. The review is complete; revisit evidence only where it helps
implement or distinguish a specific hypothesis.

## Preserve the release and start in the correct source directory

The current official signer archive (not in git) is **Storm v4 r2**, SHA-256:
`15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c`.
It is identical to the Storm v4 signer archive (not in git),
`dist/agent-storm-v4-linux-x86.zip` and `dist/storm-r2-linux-x86.zip`.
Its twelve source files are in **`storm/`**. Verify their manifest, copy them
to **`odin/`**, and develop there. Preserve the tested archive and source.

the preserved v3 archive (not in git) / `dist/agent-v3-linux-x86.zip` are the older v3, hash
`3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408`.
`dist/agent.zip` is v1. Root-level engine files and `make zip` are older and
do not build Storm or Odin. I handle site uploads; do not upload for me or
overwrite the official signer archive (not in git) while experimenting.

## Implement this sequence

1. **Current referee/state correctness.** Re-fetch live rules and the official
   starter. They now draw at **600 total plies including the opening**, after
   normal automatic outcome checks. Remove Storm's old 284-ply material-mode
   switch, 300-ply clock collapse and fixed 512-entry history buffer. Use FEN
   absolute ply and separate real/search/null-move accounting. Test exact cap
   precedence and long native history. Keep the old `harness/` untouched for
   reproduction; validate Odin in a separate pinned copy of the new official
   harness. Preserve a minimal rules-corrected Storm control.
2. **Legal exchanges and drawing resources.** Repair SEE's illegal king/pinned
   recaptures before increasing pruning. Remove static PeSTO +80 as grounds
   for deleting legal roots. Implement correct draw scores, canonical legal-EP
   repetition keys and context-valid TT bounds. Preserve saving repetitions
   and quiet defences. The native `83...Rg3` diagnostic and exact SEE fixtures
   have concrete acceptance tests in the build brief.
3. **Fast fitted evaluation.** Retain incremental PeSTO and add separately
   switchable, cheap corrections for king shelter/coordinated danger, pawn
   structure/useful activity, and passer/rook/king geometry. Cache correctly.
   Fit coefficients offline on broad data split by game/opening, with an
   independent reference implementation. Do not copy the untuned r3 bundle.
   Compare fixed-node and native fixed-wall quality, cost and paired games.
4. **Selective search and retry efficiency.** Keep verified LMR. Instrument
   pruning-family ablations on the reviewed quiet-defence cases. Add narrowly
   justified danger/zugzwang guards and verified sparse-endgame null searches.
   Improve one-sided aspiration widening and retry move ordering. Preserve
   the tactical wins and R22 perpetual as regression controls.
5. **Evidence-based time allocation.** Wire actual root effort into the
   existing controller. Record bounds, useful completed work, retries, aborted
   work and stop reasons. Recalibrate against the corrected long-game horizon.
   Do not just increase every budget: three-versus-nine-second probes retain
   several bad decisions, and today's losses averaged only 4.548 seconds left.
6. **Prove generalization.** Use realistic, balanced opening families and
   separate long-ending tests. Ablate against the rules-corrected control,
   then freeze the final candidate for the brief's predeclared **40-pair /
   80-game native 120s+0.5s holdout against the rules-corrected Storm control**,
   plus its separate 16-pair check against the exact original Storm release.
   Audit full evidence
   and paired statistics; an inconclusive result is not promotion. Deliver
   `Odin-v5-linux-x86.zip`, exact hashes, results, limitations and a promotion
   recommendation. Follow the detailed gates and separation rules in the brief.

## What the evidence actually says

Storm scored 6W/1D/3L on the ten platform games and 31W/4D/5L against v3 in the
old native holdout. The latter is 82.5% score on a synthetic corpus, not an
estimate of leaderboard strength. Some native starts have hanging pieces.
Several site wins conceal earlier mistakes, while R17 contains later saving
chances. R23 spent 8.970 seconds on `28.Qe2` and still missed a quiet defensive
plan. More time alone is not a demonstrated solution.

The additional conversion probes identify native `50...Ra1` versus `...Ra3`
as a concrete rook/passer-coordination diagnostic. The seven-piece tablebase
says native move 83's `Rg3` draws and `Rf4` loses.
Storm deletes `Rg3` before searching. Controlled cold-TT probes choose it at
both three and nine seconds when all legal roots are available. Four other
drawing moves survived the filter, so do not claim that filtering alone forced
the loss. The separate attempted reference label for **61...Kg8 is invalid**
because its PV violated the root restriction; it is explicitly excluded.

Use `reference-confirmed.jsonl` for the strongest finite-budget site labels,
and `reference-conversion-confirmed.jsonl` for the four added native roots:
individual UCI score events preserve bound flags and final-bestmove agreement.
The larger screen/first deep pass are exploratory. Even an exact UCI score
bound is not game-theoretic truth. The external engine does not model every
future competition-specific intended-move claim/cap branch. Do not hardcode
reference moves or ship the diagnostic data as a runtime answer database.

## Runtime and tool context

Use installed Python 3.12 at
`python`.
The Windows default Python may be 3.14. Windows timing is development evidence;
release packing and performance gates require Linux x86-64, one core, 2 GiB,
current fixed packages, clean caches, no network and one thread. Reconfirm
the live 90-second init budget and all mutable rules before relying on them.

Existing tools are in `lab/storm/` and `lab/odin/`. `gates.py` supports
`STORM_SOURCE`; `test_selectivity.py` supports `--engine`. Several other tests
import `storm/` directly: ensure tests actually exercise Odin. The old
`validate_holdout.py` hardcodes r2/v3 hashes, indices160–179 and forty games;
it cannot validate the new match without a separate appropriate validator.
The paired-statistics helper alone does not check all run/referee metadata.

The Linux signer previously worked. Its private connection information remains
local; use only the established destination, never guess logins or publish
credentials. The previous remote stage was `$HOME/chess-sign-storm-r2-20260904`,
Python `$HOME/chess-tk/.venv/bin/python`. Check current resource availability
before new runs. All matches, reference analyses and Storm probes from this
review finished; no engine jobs were intentionally left running.

Offline Stockfish 19 is available under
`a Stockfish binary kept outside this repository`.
Its provenance is recorded in `lab/odin/reference-engine-provenance.json`.
It is for allowed offline analysis/training/sparring only, never the submission.
The old `dist/storm-eval-r3/` experiment remains unpromoted: it cost 65% extra
Windows search time and had one Windows cold-init loss; it was not tested
as a native release. Do not confuse it with Odin or infer a Linux failure.

Proceed with implementation and measured improvement. I want a serious bid
for the top of the field, with creative work supported by evidence. Do not
promise rank one from local tests; earn the strongest candidate we can build.
