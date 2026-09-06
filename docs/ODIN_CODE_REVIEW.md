# Odin implementation audit of the frozen Storm v4 source

Reviewed 5 September 2026. This is a read-only engine audit and an implementation
brief for the next agent. No Storm source or release archive was changed. Exact
source hashes are in `lab/odin/code_review_root_filter.json`. The game-review
report supplies independent position judgements; this document distinguishes
demonstrated helper behaviour from hypotheses about the cause of a game loss.

## Findings that should shape Odin

Storm's selective search already has real late-move reductions with full-depth
verification. Replacing that with another generic alpha-beta implementation is
unlikely to be the best starting point. The strongest concrete opportunities
are to repair referee-state handling and SEE, improve the evaluation of the
positions that cost points, and measure actual decision uncertainty at the
root. Retain the proven move representation and exact make/unmake foundation.

### 1. The live 600-ply draw rule makes several inherited assumptions wrong

The freshly fetched contract and official starter now say `board.ply() >= 600`
ends in a draw, with normal `board.outcome(claim_draw=True)` checked first.
The opening's plies count. Primary evidence is saved in
`lab/odin/live-agent-contract.md`, `live-harness-referee.py.txt` (lines 58–62),
and `live-harness-rules.py.txt` (line 6). The vendored harness was not edited.

Affected release paths:

- `storm/history.py:18–20,43–44`: the old 300-ply counter and 16-ply window
  switch to a different evaluator after roughly 284 served-game plies.
- `storm/agent.py:58–60,92–93`: that one root flag controls both the raw
  "winning" classifier and the entire recursive search.
- `storm/core_nb.py:702–718`: all late leaves use only P1/N3/B3/R5/Q9 material.
  The recursion has no exact cap-distance terminal test at all.
- `storm/storm_clock.py:22,37–49`: the old cap collapses the remaining-decision
  forecast to one at played ply 299 and thereafter. With 20 seconds remaining,
  `allocation(20000,300,phase=0)` returns 18.925 seconds soft / 19.6 seconds
  hard, even though the new referee may permit almost another 150 moves.
- `storm/core_nb.py:1749–1765`: history has fixed capacity 512 but is populated
  with the entire real history and extended by search. With 600-ply games,
  a long real history plus up to 96 search plies can exceed capacity. Once
  pre-root history itself reaches 512, even the root's append is outside the
  allocation. Numba's default unchecked array access makes this a potential
  memory-corruption problem, not only an incorrect chess score.

Build Odin with separate absolute referee ply and search-stack ply. Obtain the
former directly from `board.ply()` / `2*(fullmove_number-1)+(not turn)`, which
is observable in every served FEN. Pass it into search; decrement remaining
referee plies only for legal moves, not artificial null edges. Check ordinary
terminal outcomes before the 600-ply draw, matching the starter's precedence.
Remove the old early material-evaluation mode instead of merely changing
300 to 600. Size history from the real-history length plus `MAX_PLY` and a
small explicit guard, or retain only a correctly bounded reversible window.
Do not throw away positions that still affect a referee claim.

Gate: differential terminal tests versus the freshly fetched official referee
at absolute plies 598/599/600, both colours, nonstandard starting fullmove
numbers, mate delivered on the cap move, draw claims, and null-search paths.
Use bounds-checked native testing and sentinel restoration with long legal
histories and maximum search ply. Extend clock simulations through 600 total
plies. Expected recurring cost: a few integer operations and less than a few
kilobytes of history storage; correctness takes precedence here.

### 2. SEE can reject a safe capture because an illegal recapture is counted

`storm/core_nb.py:847–917` finds the least valuable geometric attacker without
testing absolute pins or king capture legality. The Python fallback has the
same design at `storm/search_nb.py:105–169`. The following examples are
reproduced by executing the unmodified function bodies with their Numba
decorators removed, without importing or compiling the engine:

| FEN and move | Current SEE | Legal immediate recaptures |
|---|---:|---|
| `5k2/6p1/8/8/8/8/1B6/4K1R1 w - - 0 1`, `g1g7` | -400 | None; `Kf8xg7` walks onto the bishop's diagonal |
| `4k3/4b3/3p4/2B5/8/8/8/4R1K1 w - - 0 1`, `c5d6` | -200 | None; the e7 bishop is absolutely pinned to e8 |

Both are legal nonchecking captures of an undefended pawn. Their immediate
exchange gain is +100. Current quiescence rejects both at
`storm/core_nb.py:1122–1127`; shallow non-PV main search can also reject them
at lines 1376–1387. This demonstrates a helper defect and pruning consequence;
it does not establish which recorded game mistakes were caused by it.

Build legality-aware SEE / threshold SEE. Recompute occupancy-dependent x-rays,
exclude illegal pinned recapturers, allow movement along the pin ray where
legal, and reject a king capture onto an attacked square. Preserve en passant
occupancy changes and account for promotion during a recapture sequence.
An acceptable staged implementation is a cheap geometric result for ordering
and a conservative legality-aware confirmation before using a negative SEE
to discard a move. Do not replace this with unrestricted legal capture-tree
generation on every search node.

Gate: the two fixtures above, mirror/colour transforms, en passant discovered
checks, pinned sliders capturing along their pin, multiple x-rays, defended
king recaptures and underpromotions. Compare the optimized helper against a
slow legal-exchange oracle on generated legal positions. Run actual native
qsearch tests demonstrating that the safe captures remain available. Measure
the total search cost on held-out tactical and positional roots, then screen
games. Keep correctness fixtures even if a faster variant wins the games.

Reproduction: `lab/odin/code_review_repro.py` and `.json`. This is source-isolated
Python evidence, not a substitute for Odin's compiled regression gate.

### 3. Replace hard draw-avoidance move deletion with rule-aware search scores

The current root policy is based on a **static PeSTO** score of just +80 cp,
not on a searched proof that the position is winning:

- `storm/agent.py:58–66` computes the classifier before search.
- `storm/history.py:191–198` removes every nonzeroing move from halfmove 90,
  every move to any previously seen position, and certain claim-enabling moves.
- If one move survives, `storm/agent.py:80–81` plays it without search.
- If all moves fail the policy, `storm/history.py:200` restores the entire
  original legal set. These discontinuities are heuristic, not referee rules.

A read-only replay of all ten day-two games and all forty native games found
137 roots with a removed move. Six were in day two: R21 moves 36/53/55, R24
move 60, and R25 moves 40/45. None of these games triggered the halfmove-90
zeroing-only restriction. Thus that restriction is a structural concern, not
an established explanation for today's score.

There is an especially useful native-loss diagnostic. In opening 165.2,
Storm Black at move 61 has FEN
`R4k2/5p2/6p1/4P2p/5K1P/5P2/p7/r7 b - - 5 61`.
There are only two legal moves. Static PeSTO is +249 cp; the policy deletes
`f8g8` because the resulting position has appeared before and forces `f8e7`
without search. Compare these with full original history and an independent
reference engine before asserting a lost win. The replay alone does not say
that `Kg8` wins or that `Ke7` loses.

Build a root search over all legal moves, with actual immediate terminal
results assigned their correct scores. A draw is preferable to a loss even
when raw PeSTO says +80. Use a searched winning alternative to justify
avoiding a draw; never ban all quiet moves nine plies before a claim as a
substitute for evaluating the resulting pawn move or capture. Preserve the
root legality firewall and instant genuinely forced legal replies.

At internal nodes, `is_repeat` (`core_nb.py:829–833`) returns draw on **any**
prior occurrence, whereas a second occurrence alone is not a referee draw.
The lightweight fixture `Nf3 Nf6 Ng1 Ng8` from startpos has no claimable
outcome but trips this helper. This common cycle-shortcut policy must not be
presented as exact referee modelling. Distinguish a true threefold/claim-by-
intended-move terminal from optional cycle heuristics. On nodes where some
history key has two occurrences, test whether a legal child completes the
referee claim; the referee stops before the agent can choose a different move.

Use a canonical repetition key. The current raw en-passant Zobrist component
at `core_nb.py:299–301,342–344` differs for the same position with an impossible
EP square, while python-chess's repetition key is identical. Reproduction:
the position after `e4` with `e3` versus `-` in the EP field. The Python root
Counter already uses python-chess's canonical key, so root and native search
currently disagree. Exclude the EP square when no legal EP capture exists,
including the pinned-EP case.

Gate: full PGN-history replay against `board.outcome(claim_draw=True)`, second
versus third occurrences, intended-move claims, impossible/legal/pinned EP,
quiet mate at halfmove 99, sacrificing to escape a loss despite a positive
static score, and draw avoidance only when a better searched continuation
exists. Retain the recorded native 61st-move position as a diagnostic with its
history, not as a hardcoded best-move answer.

### 4. The TT needs explicit rule and history context

`storm/core_nb.py:796–825` stores only the position key, move, score, depth,
bound and generation. The key excludes the halfmove clock and absolute ply.
`tt_probe` does not reject a stale generation; generation currently controls
replacement, not validity. Node repetition checks before TT lookup correctly
catch some direct draws, but do not make a predecessor score independent of
the reversible path leading there. A bound backed up from a repetition or
near-rule-50 continuation can be reused in a context where it is wrong.

Build and test a context-valid score cache separately from move-order reuse.
At minimum, include rule-50 and cap-distance context where they affect the
searched horizon. For a correctness-first reference implementation, include
a reversible-history/count signature in the score-cache identity; hash-move
ordering can remain available across contexts after legality checking. A
lighter safe cutoff guard is an optimization only after it passes the same
differential fixtures. Merely clearing TT once per real move does not resolve
different paths inside that move. Merely adding the current repeat count does
not represent which other positions can complete a claim.

Gate: cold versus prewarmed TT on identical boards with halfmove clocks 0/98,
different prior histories and absolute cap distances; transposing reversible
paths; promotion/EP/castling keys; normal mate-score distance conversion;
interrupted searches must not store an unproven exact result. Compare against
a TT-disabled shallow reference. Record the speed/memory cost of stricter
context; a small extra field/hash is affordable under the measured ~414 MiB
baseline, but hit-rate loss may cost search depth.

### 5. Preserve verified selectivity, improve the weak parts independently

The LMR full-depth fail-high verification is present at
`storm/core_nb.py:1463–1492`, followed by a full PV-window re-search when
appropriate. Keep it and `lab/storm/test_selectivity.py`'s false-cutoff test.
Do not describe LMR as the missing technology: Storm already ships it.

Null-move pruning (`core_nb.py:1291–1339`) has a static-eval gate and guards
against consecutive nulls, but accepts a fail-high without verification.
`has_nm_pieces` allows any rook or minor, so disabling it only in pawn-only
positions does not protect sparse rook/minor zugzwangs. Add a controlled
verification search for vulnerable low-material cases and isolate repetition,
rule-50 and cap accounting on artificial null paths. Test against known legal
zugzwang fixtures and matched pruning-off probes. This should follow SEE and
rule-state correctness, and its cost should be measured separately.

The current root aspiration window is +/-25; any failure immediately retries
the full window, and the retry still orders the old completed-iteration best
at `core_nb.py:1831` instead of the just-found fail-high move. Implement
one-sided geometric widening with the returned bound move as the retry's
ordering hint, while keeping the last completed exact iteration as the legal
fallback. Record failure direction, retry count, nodes and completed depth.
Gate identical full-window results on a fixed-depth suite, bounded deadline
overrun and no extra compilation on a retry; screen whether saved work buys
more correct decisions under the same wall clock.

Move ordering currently sorts all captures ahead of killers and quiets using
MVV/LVA (`core_nb.py:921–964`), including losing captures. After SEE is correct,
consider a staged picker: legal TT move, useful tactical moves, killers/good
history quiets, then losing captures and remaining quiets. This is a targeted
efficiency experiment, not a required rewrite before evaluating Odin's chess
improvements. Existing insertion sorting allocates two small arrays at every
node, so measure allocations/cost before adding another per-node array.

### 6. Build a cheap, calibrated evaluation correction, not the entire r3 bundle

The deployed native evaluator (`core_nb.py:673–718`) is exact incremental
material/PST plus tempo; it has no representation of pawn blockers, passer
stopping distance, rook support, king shelter or coordinated attacks.
This is an explicit representational limitation. Which term should come first
depends on the independent game review, not on interpreting a PeSTO score as
an objective evaluation.

Odin should keep the validated incremental PeSTO accumulator and add separately
switchable corrections with an independent Python reference. Start with the
features justified by the reviewed error families: pawn structure/passed-pawn
geometry and king distances for conversion, and queen-scaled king shelter /
coordinated danger for middlegame exposure. Cache pawn-only work by a pawn key;
king-dependent terms need king squares in that cache key or separate evaluation.
Reuse attack information rather than scanning all slider mobility at every
leaf. The prior r3 bundle took 65% more time locally and must not simply be
copied into production as a unit.

Fit coefficients offline on broad, independent positions, using independently
produced reference labels when appropriate. Split by game/opening before
training and keep today's reviewed games as diagnostics, not as the only
training data or final holdout. Ship original code and learned coefficients,
not a lookup database of engine answers. Maintain symmetric colour transforms,
bounded scores below mate bands, exact incremental undo, finite integer scores
throughout the native/TT boundary, and independently checked phase tapering.

Do not silently put a richer evaluator only in the native path while the
Python/root path still makes hard decisions with old PeSTO. Removing the raw
root filter addresses its worst consequence; reference and fallback evaluation
must still agree. Evaluation scale also governs RFP, forward futility, SEE
margins, aspiration and time-manager score-change thresholds. Measure and
calibrate those scales; new features do not license tightening pruning.

Gate each feature block independently: symmetry and make/unmake, held-out
prediction error, annotated difficult roots at fixed nodes and fixed wall time,
native per-search overhead, then fresh paired games. An initial engineering
target of roughly 10–15% added native search time is useful; a measured larger
cost is acceptable only if an independent playing-strength gain justifies it.
The old r3's Windows init failure is not evidence that a smaller new evaluator
fails Linux initialization; test clean native imports of Odin itself.

### 7. Make the time manager observe decision difficulty at the root

`SearchClock` exposes a `root_effort` input (`storm_clock.py:109–129,165–168`),
but `core_nb.search_root:1858–1859` never supplies it. Current uncertainty is
therefore inferred only from successive best moves/scores and aspiration
failures. The manager also has no bound-aware top-two score gap, failed retry
cost or measure of how much of the last search was abandoned.

Instrument per-root move nodes, time and bound type inside `root_search_nb`,
using one persistent array per root search rather than allocations per node.
Record completed-iteration PV move/score, aspiration retry work, final aborted
iteration work and stop reason. Feed the actual best-move node share into the
existing input. A null-window bound is not an exact second-best score; obtain
a score gap only where the search actually establishes one, or use its bound
with correct uncertainty.

Recalibrate the remaining-decision forecast with the actual-site/long-game
distribution and the corrected 600-ply rule. Preserve some bank for rook and
queen endings with several viable plans; sparse material alone is not easy
chess. Test smaller aspiration overhead and more predictive iteration launching
before simply raising the hard/soft multiplier. One observed move may exceed
the final printed soft target because an iteration runs toward the hard
deadline; that is expected by this controller, so measure useful completed work
and abandoned work instead of declaring every soft overshoot a timeout bug.

Gate: deterministic synthetic traces, long-game budget simulation, deadline
tests with abort restoration, and paired real-opening full-clock ablations of
clock-only changes. Compare decision quality and result, not merely seconds
left. Keep diagnostics compact because the site retains only the first/last
4 KiB of stdout/stderr.

## Build order and evidence separation

1. Preserve all frozen Storm/v3 archives. Create Odin source separately.
2. Correct the live cap/state/buffer logic and its independent reference tests.
3. Repair SEE and rule-aware draw/TT handling in separate testable commits or
   snapshots. This is the foundation for subsequent search claims.
4. Add bounded root telemetry and aspiration retry improvements; verify their
   node/deadline behaviour before changing allocation policy.
5. Develop the cheap evaluation blocks motivated by the independently reviewed
   games, ablate and calibrate them, and test endgame null verification.
6. Tune clock policy with the new telemetry; changing evaluation, pruning and
   time thresholds all at once makes the cause of any gain uninterpretable.
7. Freeze candidate bytes before a new native full-clock holdout against exact
   Storm. Use unseen, realistic paired openings and longer endings; retain
   synthetic starts as a separate stress corpus. Match against v3 remains
   historical evidence and cannot be Odin's promotion baseline.

The existing 40-game result remains valid evidence about Storm versus v3 under
the old recorded referee. It is not validation of a 600-ply referee model and
must not be reused as Odin's final holdout after diagnostics have been mined.
No claim here establishes that Odin will reach rank one; the proposed work
turns specific observed/code-supported weaknesses into falsifiable improvements.

## Follow-up: controlled Storm probes after the independent game review

`lab/odin/storm_diagnostics.py` ran the exact twelve frozen source files,
verified against the Linux release manifest, on Windows Python 3.12 with CPU 2
affinity and one-thread environment settings. Native warmup succeeded in
63.188 seconds without a readiness override. These are local decision probes,
not Linux performance evidence or a new match.

Each root reconstructed the actual served/returned repetition history through
Storm's original history APIs. No preceding engine searches were rerun. TT,
killers and heuristic history were cleared before **every** root and allowance.
Thus these probes do not reproduce the original game's TT contents or
ordering statistics. Both hard and initial soft allowances were 3,000 or
9,000 ms; the unchanged controller could finish sooner. Actual times, every
root aspiration call's bound, completed depth and abort status are retained.

| Position | 3-second allowance | 9-second allowance |
|---|---|---|
| Site R17, before 59...Bf8 | Bf8, d10, -91 cp, 1.654 s | Bf8, d12, -105 cp, 6.097 s |
| Site R17, before 64...Be7 | Be7, d11, -163 cp, 2.054 s | Be7, d15, -198 cp, 6.397 s |
| Site R23, before 28.Qe2 | Nf5, d10, +94 cp, 1.716 s | Nf5, d13, +74 cp, 8.940 s |
| Site R23, before 30.h4 | h4, d9, +52 cp, 2.310 s | h4, d11, +35 cp, 8.895 s |
| Site R16, before 24.Qe2 | Qe2, d9, +41 cp, 1.977 s | Qe2, d10, +36 cp, 5.734 s |
| Site R18, before 21.Qd1 | Rxc6, d10, +13 cp, 2.334 s | Rd1, d12, -1 cp, 6.547 s |
| Native 165.2, before 83...Rf4, original root filter | h2, d12, -146 cp, 3.001 s | Rf4, d13, -167 cp, 6.360 s |
| Same native position, all legal roots | Rg3, d17, 0 cp, 2.438 s | Rg3, d20, 0 cp, 6.078 s |

Scores in this table are Storm's own side-to-move scores, not reference values.
The site positions that retained Bf8, Be7, h4 or Qe2 despite the larger
allowance demonstrate why extra thinking alone is not an adequate prescription.
The different cold-TT choices at R23 move 28 and R18 move 21 also show why a
FEN-only rerun cannot be called a faithful replay of the original decision.

The seven-piece native root before 83...Rf4 is
`2k5/4K3/6P1/8/4p3/5r1p/R7/8 b - - 5 83`.
The independent tablebase record (`tablebase-opening165-move83.json`) says the
root is drawn, ...Rg3 preserves the draw and ...Rf4 loses. The original filter
excludes ...Rg3 but leaves **four other drawing moves** available. It is
therefore wrong to say the filter alone forced the loss. These controlled
probes show that the root restriction and search valuation interact: the
unfiltered searches find a draw, the filtered three-second search also finds
a drawing ...h2, and the filtered nine-second search chooses the losing ...Rf4.
This is a useful regression target for joint rule-state, SEE/search and
evaluation work, not evidence for a universal "more time makes Storm worse"
claim. Tablebase draw claims retain their ordinary-chess/rule-50 scope; the
full recorded history must still be checked against the competition referee.

No source file changed during or after the probes. The full diagnostic record
is `lab/odin/storm_diagnostics.json`.

## Follow-up: independent reference-measurement audit

`lab/odin/code_review_measurement_audit.py` replayed all **6,221** recorded
reference-screen positions across fifty games, plus all **34** selected deep
roots across nine games. Source digests, player colours, complete available
PGN move histories, served FENs, played moves and legal PV replay passed.
Both files were complete at the audited snapshot. `game=object()` in the
reference helper triggers a new UCI game before each search, so searches do
not intentionally share position TT state. Node counts are limits: trivial
mate lines can finish below their allowance, while ordinary searches have
small overshoots; they are not all exactly equal-node results.

The audit found one concrete invalid restricted-root result: deep native
165.2 at ply 111 (before 61...Ke7), requested alternative `f8g8`, returned a
PV starting `f8e7`. Its score/nodes/PV match the unrestricted search. Quarantine
that alternative result; it is not evidence about ...Kg8. A follow-up should
record the UCI request and verify the returned first move, or analyse the
pushed child with full history. The audit did not find such a mismatch in
the recorded played-root results.

Important numeric limitations:

- `reference_review.py:score_info` discards UCI `lowerbound` and `upperbound`.
  Its saved scores cannot retrospectively be certified exact. python-chess's
  `analyse` result aggregates successive info dictionaries, so a depth, score,
  PV or bound flag can originate in different updates. For decisive follow-up
  labels, stream info and retain the last **score-bearing event** with that
  event's own depth/PV/bound flags, plus the final best move. Simply reading
  the aggregated bound flag is insufficient because old flags can persist.
- A forced-move search can give that move more useful work than an unrestricted
  search with the same total node limit. Three deep records score the forced
  move 2/7/18 cp better than the unrestricted search of the same best move.
  These are ordinary finite-search inconsistencies, not negative regret or
  evidence that the selected alternative is worse.
- Current-root automatic outcomes are correctly overridden with python-chess,
  but Stockfish's internal future search is not the competition's mandatory
  claim-by-any-intended-move plus 600-ply terminal model. No retained deep PV
  was observed continuing past a current referee claim within its saved
  sixteen plies; this limited check does not validate unseen search branches.
- Stockfish WDL values are its calibration model, not this tournament's win
  probabilities. Mate scores should not be mixed into ordinary centipawn-loss
  averages. Low-node screens are a discovery tool; important labels need the
  deeper confirmations and, where available, tablebase verification.

Audit artefact: `lab/odin/code_review_measurement_audit.json`. These limitations
do not invalidate the game replay or the overall review. They set the strength
of the chess claims that can be supported by the retained measurements.
