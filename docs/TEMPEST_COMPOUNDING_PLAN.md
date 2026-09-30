# Tempest: compound measured edges around the narrower search

6 September 2026. The signer archive remains released Tempest r1. This is an implementation
sequence, not a claim that its proposed components are already stronger.

## What the promising result does and does not establish

`lab/tempest_attack/prototypes/pawn_lmr` exempts quiet pawn pushes near the
enemy king from late-move reductions. Everything else remains Tempest r1.
Its 16 development games at 500 ms scored 5W/7D/4L (53.125%). That nominates
it for further work, not promotion. At one million nodes it avoided the R37
Qxa5 error; at four million and 9.4 million it returned to Qxa5. The desired
attack recognition is not yet stable across search budgets.

The combined futility exemption scored 3W/8D/5L. The cheap learned quiet-order
prior scored 2W/11D/3L. Do not add either to the stack merely because it exists.
See `TEMPEST_FRONTIER_RESEARCH.md` for their evidence and limitations.

## First implemented experiment: make the same search cheaper

`lab/tempest_stack/stage.py` freezes a two-by-two experiment:

| Variant | Change from the narrower candidate |
|---|---|
| narrow | Exact frozen control |
| lazy | Calculate the pawn exemption only when the other conditions produce a nonzero reduction |
| packed | Replace the two move-sort key arrays with one exactly equivalent signed 64-bit key |
| both | Both changes together |

The lazy predicate is evaluated after making a quiet pawn move: that move
cannot change the opponent king square or the identity/destination of the
mover. The sort encoding preserves every category and signed secondary key;
stable ties remain stable. Neither change deliberately changes the search tree.

Gate: native readiness, six depth-three perft positions, stable-sort reference
checks with ties/killers/hash and signed histories, board restoration, ABA state
isolation, and exact fixed-node search identity including all completed
iterations. Two Linux cores run opposite candidate orders; 12 used diagnostic
roots, two repeats each, 200k nodes. Complete every trial. A timing claim
requires a positive geometric-mean speed effect in each lane. Small effects
still need broader isolated-host confirmation before predicting game gains.
Completed results are in `lab/tempest_stack/result.json`:

| Variant | Geometric mean search speed relative to narrow | Lane A / B |
|---|---:|---:|
| lazy | 1.0219x | 1.0256x / 1.0182x |
| packed | 1.0159x | 1.0185x / 1.0132x |
| both | 1.0192x | 1.0248x / 1.0137x |

All 192 fixed-node runs matched the control's move, score, depth, node count,
abort state and every completed iteration's move/score/node work. All 768
ordering checks and 48 perft checks passed; native cold imports were
34.45–35.31 seconds. This is repeated evidence on 12 roots, not 192 independent
positions. Both lane orders were positive, but the effects are small and the
combined version did not exceed lazy alone. Prefer lazy as the simpler next
development base; do not claim statistical superiority over the combined arm
or translate this timing result into Elo. A broader performance confirmation
is still appropriate before a release speed claim.

This creates a possible throughput edge without confounding it with changed
move choices. It does not validate the narrower chess policy itself.

## Next three separable chess experiments

### 1. Spend the protected depth more selectively

Build from the fastest identity-passing variant, if any. Compare separately:
(a) current full exemption; (b) full exemption only when the pushing side still
has a queen; (c) reduce the ordinary LMR reduction by one rather than removing
it entirely. Keep the existing advanced-pawn/check/killer/hash protections.
Do not change futility or evaluation in these arms.

The hypothesis is that preserving one extra ply, or avoiding low-value pawn
exemptions in queenless positions, can retain useful attack coverage at lower
cost. Neither is known to help. Check both colours, king moves, queen trades,
and the threshold boundaries. Evaluate actual equal-wall choices at several
budgets, including longer budgets where the present R37 repair disappears.
Use those site cases only as diagnostics; add diverse used-development roots
before selecting. Do not optimize only for Qc2 or Qh2+.

### 2. Retain expensive search results instead of overwriting collisions

The current 2^22-entry table has one slot per index. `tt_store` preserves a
deeper same-key entry in the current generation, but a different colliding key
replaces it regardless of depth. First instrument collision eviction depth,
age, useful hits and cutoff reuse in a lab-only build. If valuable evictions
are material, implement an original two-slot bucket with the same total entry
count and existing score/move layout. Probe both full keys; select replacement
using generation distance and depth, rather than increasing memory.

Gate dependencies: collision and age-wrap tests, full-key verification, mate
distance conversion, exact/lower/upper bound validity, cap-aware keys, and
repetition precedence. Extra probe work can cost more than it saves; compare
equal wall time. This is a distinct candidate, not part of the identity claim.

### 3. Learn capture ordering from this game's search

The current capture order is static victim/attacker value, ahead of killers
and quiet history. Prototype bounded online history indexed by moving piece,
destination and captured piece. Reward a searched capture on beta cutoff and
apply bounded maluses to earlier searched captures; preserve the TT move's
priority, promotions and qsearch legality. Start by using history only to
resolve equal static capture ranks, then measure activation and first-move
cutoff rate. Never train on captures skipped by pruning as if they failed.

This differs from the earlier blanket SEE-ordering experiment and the failed
learned quiet prior. It targets live tactical ordering, not a static quiet-move
prediction score. Require state reset tests, history bounds and actual useful
activation before a match. Widen its influence only as a separately named arm.

## A fourth, orthogonal frontier: endgame judgment

R38's entire 101-position five-piece phase was tablebase-drawn. Its positive
material evaluation was not a missed forced win. Use balanced endgame training
and/or measured tablebase coverage to improve decisions *before* entering such
endings, not a contempt adjustment that relabels a theoretical draw as a win.
The live rules previously fetched permit shipped books/tablebases; re-check
before packaging and measure exact sizes, imports and missing-table behavior.
Do not claim that a complete four/five-piece set fits the archive without an
actual file inventory. Runtime reference API answers remain outside the agent.

## How to establish compounding without 112 games for each knob

For each nominated addition B, compare the current stack A against A+B on
identical development openings with colours reversed and equal wall budgets.
When two additions survive individually, run A, A+B, A+C, A+B+C; measure the
bundle against A, not merely against the older release. Retain every result.
Do not add percentage win rates or turn a noisy screen into a precise Elo claim.

Use cheap correctness and decision diagnostics to reject bad ideas early,
short paired games to nominate a small number, and spend the fresh confirmation
set only after source/configuration freeze. The existing 12-family fresh set
must remain unopened during this development selection. Strongest bundle then
faces the actual released Tempest r1 at full clocks and the Linux archive gate.
If a bundle helps only at 500 ms, that is not enough for a site replacement.

## Avoid rediscovery

One-sided aspiration retries and root-work clock telemetry were built in the
original Odin effort and later screened; they are not new omissions discovered
today. The current clock already reacts to stability, score changes and
iteration cost. More spending needs game-level evidence: R38 reached 2.88 s,
so the old story that every game wastes 25 s no longer describes this sample.
Increasing pressure weight, removing the evaluation clip, relaxing futility,
and the cheap policy model already failed relevant screens. Revisit only with
a changed mechanism and an explicit new hypothesis.
