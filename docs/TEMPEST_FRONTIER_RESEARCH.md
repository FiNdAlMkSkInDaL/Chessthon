# Tempest frontier research — 6 September 2026

**Desktop release remains Tempest r1**, SHA-256
`0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4`.
Nothing from this research has been promoted. Canonical released source remains
`tempest_exact/`. Research lives in `lab/tempest_attack/`.

## What the attack investigation established

The new Neural Gambit loss was not repaired by simply increasing the fitted
evaluation cap from 400 to 1,600 cp. The completed 16 fixed-node probes of that
variant matched the baseline's moves and scores. Multiplying the existing
king-pressure weight by four also failed the diagnosis: it chose ...Kg6 after
Qxa5, which the 2M-node reference rates around +0.53 for Black versus approximately
+8.7 for the forcing attacks. Making a pressure number larger is not a solution.

The baseline's TT continuations after Qxa5 ...Qh2+ Kf1 included ...Bb7 or ...Rf8,
missing the power of ...f4. Separate forced comparisons at the latter root:

| Black move | Native score, 1M nodes | Reference score for Black, 2M nodes |
|---|---:|---:|
| ...f4 | +3.34 | +8.68 |
| ...Bb7 | −1.09 | 0.00 |
| ...Rf8 | −0.60 | +0.48 |

The unrestricted native search at that later root does find ...f4 (+1.91).
This localizes an important horizon/selection problem: the resource is found
when it is closer to the root. It does not prove that evaluation is otherwise
correct. The reference's unrestricted and forced scores also differ, so none
of these centipawn figures is game-theoretic truth.

**TT continuations are diagnostic, not certified completed PVs.** They include
entries left by the aborted final iteration; bounds and depths are retained.
Do not report spectacular mate scores at their tails as the root's assessment.

## Targeted search experiment and negative controls

We tested a geometric class of quiet pawn pushes: destination within one file
and three ranks of the enemy king. No move/FEN/opponent lookup is used.

- `pawn_threat`: exempt this class from both quiet futility and LMR.
- `pawn_lmr`: exempt it from LMR only.
- `pawn_ff`: exempt it from quiet futility only.

At 1M nodes, LMR-only changed Qxa5 to the reference-preferred Qc2 and raised
Black's assessment after Qxa5 from −0.94 to +2.70. The combined change recovered
...Bd7 in the earlier AI Fellows diagnostic; futility-only also recovered that
move, but did not repair the Neural Gambit attack assessment.

**The Qc2 result is not stable.** A further Linux check at 4M and 9,432,064
nodes returned to Qxa5 with LMR-only. At the largest budget its score was −3.34,
and Black's opponent-side score was +5.07. Baseline also finds ...f4 with more
budget. This is evidence of improved coverage in a difficult subtree, not a
durable repair of the original decision.

Completed independent game-log replay and source/reset checks:

| Candidate vs released Tempest r1 | Development search allowance | W / D / L | Score | Decision |
|---|---:|---:|---:|---|
| Combined pawn protection | 100 ms | 3 / 8 / 5 | 43.75% | Reject promotion testing |
| LMR-only pawn protection | 500 ms | 5 / 7 / 4 | 53.125% | Inconclusive; no promotion |
| Learned quiet prior | 500 ms | 2 / 11 / 3 | 46.875% | Reject promotion testing |

Each was a predeclared **16-game, eight-pair** screen on used development
openings, completed without outcome-dependent stopping. All 2,735 and 1,983
plies respectively passed legal replay, actual-referee terminal checks,
source/data identity and persistent-worker reset audits. They are different
time controls and candidates; **do not pool them or claim precise Elo**.
Linux workers used one pinned core per active mover; two lanes ran within a
3 GiB/no-swap group. These are not full-clock competition tests.

## Original attack evaluation pilot

Fourteen original coordination features covered weak king-ring squares,
checking opportunities, supporting attackers, pawn levers and open king files.
Five opening-family folds compared six nonnegative Huber/ridge fits over 5,288
existing labelled search states. **All old train/validation/test sets are now
used development data**, not a new untouched test.

Best development MAE improved only about 1.93 cp (273.91 → 271.98), below the
predeclared 5 cp gate. Endgame and quiet tails did not materially deteriorate,
but the average improvement did not earn native integration. No weights ship.
The constrained solver includes convergence/KKT checks; feature color-mirror
symmetry was checked on all included boards.

## New lever: learned quiet-move ordering

Rather than adding a costly leaf evaluator, a new original conditional model
learns to order quiet moves from existing offline reference labels. It covers
4,064 eligible decision states, 102,683 legal quiet alternatives and 564 opening
families. Teacher-best quiet moves are approximate preferences, not measured
regret margins. There is no runtime move/FEN database.

Four predeclared five-fold development fits compared linear and piece-conditioned
models. The selected full model placed the reference choice in the top three
41.95% of the time, compared with 26.72% for a PeSTO-delta control; reciprocal
rank rose from 0.2615 to 0.3726. These are **ordering proxies, not strength**.

A cost ablation removed full attack scans, check testing and king-zone changes.
The smaller model retained 33.74% top-three and 0.3117 reciprocal rank, passing
the predeclared development threshold. Its coefficients collapse into six
13-value rows, one row per moving piece type.

The native prototype uses this model **only to break zero-history quiet-move
ties**. TT moves, captures, killers and all nonzero history priorities dominate.
It leaves evaluation, LMR, futility and clocks unchanged, and starts directly
from Tempest r1 rather than stacking an inconclusive pawn-search change.

Native/reference parity passed on 7,847 quiet moves from 313 positions, with
maximum logit error 1.41e−7. History/TT priority and board restoration checks,
plus six depth-three perft cases, passed. Local ARM import took 81.04s; Linux
match-worker imports were approximately 33.6–33.9s. Full deployment gating
remains separate. The **completed 16-game 500ms match scored 2W/11D/3L**, or
46.875%, and failed its predeclared promotion screen. All 1,862 plies and four
worker identities/reset proofs passed audit. The result is too small to prove
a precise Elo loss, but it supplies no basis for replacing the release. The
attractive classification result did not establish a playing-strength gain.
Evidence: `lab/tempest_attack/match-policy/summary.json`.

## Round 38: RMFE draw

The upload archive cannot be identified from the PGN/log. Do not silently call
this an Odin-v6 or Tempest-r1 game. We played Black, drawing by fifty moves after
103...Ba8. All 191 game plies replay legally; 192 states were screened with
history-preserving 100k-node references. The minimum recorded served clock was
2,880ms, which is not a measured pre-increment deadline margin.

Same-root 2M-node comparisons confirm modest early inaccuracies:

| Decision | Played | Reference alternative | Black scores: alternative / played |
|---|---|---|---:|
| 8.Black | h6 | Nd4 | +0.09 / −0.67 |
| 9.Black | cxd4 | b6 | −0.79 / −1.22 |
| 11.Black | d5 | Nc4 | +0.21 / −0.22 |

The apparent 19...Kf8 error is not established: both unrestricted and forced
reference searches choose Kf8. Their score difference is reference instability.

After **53...Nxa5**, the five-piece KBN-v-KB position is tablebase-drawn.
**All 101 five-piece positions through the finish are draws** according to the
retained Lichess Syzygy responses. No later forced win was offered and missed.
The engine's material advantage and positive score in that phase should not
be described as a thrown-away win. This motivates broader exact endgame
coverage and score calibration, not indiscriminate draw avoidance.

References are offline postgame queries through the
[official Lichess tablebase API](https://github.com/lichess-org/lila-tablebase),
with full response URLs and FENs retained in `round38/tablebase-review.jsonl`.
No downloaded answers enter the agent or the training datasets. The current
[competition rules](https://aichessathon.com/docs/rules.md) separately permit
shipped tablebases within the 50 MB limit; feasibility and integration are still
their own work, not an existing release capability.

## Research discipline and next gates

1. All three fixed development matches are complete and audited: 48 games and
   6,580 legal plies across distinct experiments. **Do not pool their scores.**
   No candidate earned promotion or independent confirmation from these screens.
2. For ordering, instrument which moves actually have zero history and
   whether the prior improves cutoff discovery. Do not scale its influence
   merely to make the Neural Gambit move change.
3. The richer model's attack/check signals are useful in the ordering proxy.
   A later cost-controlled experiment could compute them only near the root
   or share attack masks across moves, with explicit native cost and match gates.
4. For search selection, collect reduced fail-low counterfactuals across
   unrelated games to learn which preparations need depth. The isolated pawn
   rule identifies a lever but has not established a general improvement.
5. Reserved fresh confirmation openings remain unused by this research so far.
   Do not call any of these development matches a holdout or combine their
   results with earlier generations' 112-game runs.
6. Revisit data allocation before calling the representation saturated. The
   first Tempest sampler excluded old training families as well as validation
   families, leaving only 1,131 roots. Consumed data can be reclaimed for
   development while genuinely fresh families remain reserved. Any enlarged
   corpus needs an explicit contamination map; it does not become a fresh test
   merely because it is relabelled. No enlarged corpus was generated this turn.

Setup failures remain visible: the initial fitter attempted an unavailable
SciPy import, then used an original constrained NumPy solver; initial TT-trace
inspection needed an explicit uint64 cast; the first forced-reference call
passed a string rather than a Move list and timed out. Corrected runs are
separate artifacts. None is a failed game removed from a score. Early lab
trace drivers evolved during development, so their file hashes are not a
complete immutable executable snapshot; source/driver identities remain
recorded. The later Linux depth check uses the frozen `trace_search_v5.py`.
