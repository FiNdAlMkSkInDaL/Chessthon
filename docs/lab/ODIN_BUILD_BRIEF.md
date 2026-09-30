# Odin: implementation brief for Storm's successor

Prepared 5 September 2026 after reviewing all ten Storm platform games, all
40 native Storm-v3 games, the separate development matches, and the frozen
source. **This is the next agent's build assignment. Odin is not built yet.**
The existing Storm upload remains unchanged.

Read `ODIN_REVIEW.md`, `ODIN_SITE_REVIEW.md`, `ODIN_HOLDOUT_REVIEW.md` and
`ODIN_CODE_REVIEW.md` before implementation. They contain the evidence and
exact source locations. Preserve the strengths of Storm's original search;
the assignment is a stronger successor, not another rewrite of verified board
representation, legal move generation and incremental make/unmake.

## Success criteria and working layout

Create `odin/` from the exact tested `storm/` source, then make independently
testable changes. Preserve the signer archive (not in git), `Storm-v4.zip`, `v3-agent.zip`,
the old sources and native archives. Do not overwrite the official upload
while experimenting. Keep a manifest for each candidate; the workspace is
not currently a Git repository, so use distinct snapshots if not using Git.
The user handles platform uploads.

The official Storm SHA-256 is
`15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c`.
Source: `storm/`; native archive: `dist/agent-storm-v4-linux-x86.zip`.
The old root-level engine and `make zip` do not build Storm or Odin.

The goal is measurable improvement against strong play on representative
openings, with better defence, king safety and conversion. No local result
can promise first place. Do not substitute clock consumption, a feature
count, nominal depth or a matchup against v3 for demonstrated Odin strength.

## 1. Correct the live referee model before tuning strength

The live contract and official starter changed: **600 total plies, including
the opening, then a draw**. `board.outcome(claim_draw=True)` runs first.
The current official starter uses `board.ply()`, not move-stack length.
Saved evidence: `lab/odin/current-contract.md`, `current-rules.md`,
`live-source-provenance.json` and `live-harness-referee.py.txt`.
The observed starter commit is `91f70e54be07e1bf56311962044a08b822c3af50`;
re-verify upstream before beginning.

Implement these together:

- Separate absolute referee ply, played-game history length and recursive
  search ply. Obtain absolute ply from every FEN's fullmove/turn, equivalent
  to `board.ply()`. Do not guess it from the number of our requests.
- Remove the old early switch to P1/N3/B3/R5/Q9 material at approximately
  played ply 284. This is not fixed by replacing one `300` with `600`.
  Score the exact cap as a draw, after normal terminal precedence.
- Carry cap distance through legal search edges. Artificial null moves must
  not advance the real referee counter or create fictitious game repetition.
- Replace `np.empty(512)` history storage with explicit capacity for real
  history plus maximum recursive depth and guards, or a rigorously bounded
  reversible-history window. At pre-root history 418, deep native search can
  already exceed the old array; at 512, the root append itself is out of bounds.
- Remove the clock's old collapse to one remaining decision at played ply
  299. Keep phase/game-age forecasting separate from the actual cap limit.

Use a **separate, commit-pinned copy of the new official validation harness**.
Do not hand-edit the historical `harness/` or break reproduction of Storm's
old audit. Ensure the match process actually imports the new pinned harness;
log module paths and hashes. The first tests must compare its real behavior
with Odin at plies 598/599/600, nonstandard starting fullmove numbers, both
colours, mate on the cap move, fifty-move and prospective repetition claims.
Add bounds-checked native long-history search and exact undo tests, plus a
600-ply clock simulation. These are concrete new defects, not an invitation
to spend the whole project on generic operational checks.

Retain a minimal **rules-corrected Storm control** after this stage. It helps
separate strength gains from winning long games because the old baseline
uses the obsolete rule. It must have its own name/hash, not replace Storm.

## 2. Repair capture and draw decisions that remove useful moves

### Legal capture exchanges

Fix `see_nb` and its fallback before tightening any capture pruning. Current
SEE counts illegal recaptures and can discard a safe pawn capture:

| Position | Move | Current SEE | Required exchange result |
|---|---|---:|---:|
| `5k2/6p1/8/8/8/8/1B6/4K1R1 w - - 0 1` | `g1g7` | -400 | +100; the king cannot legally recapture |
| `4k3/4b3/3p4/2B5/8/8/8/4R1K1 w - - 0 1` | `c5d6` | -200 | +100; the e7 bishop is pinned |

Implement occupancy-aware x-rays, legal pinned-piece movement, king-capture
safety, en passant and promotion handling. Prefer a fast threshold SEE or
conservative confirmation before negative SEE prunes a move. Do not put a
full python-chess exchange tree in the hot loop. Use a slow legal exchange
oracle only for differential tests. Include transformed versions of the two
fixtures, pinned captures along their pin, discovered checks and promotions.
Verify the actual compiled qsearch retains the safe captures. The old source
reproductions alone do not test Odin's native implementation.

### Search drawing resources instead of deleting them

Remove raw PeSTO `>=80` as authorization to ban root moves. Search every
legal root move unless a sound terminal fact resolves it. A second occurrence
is not automatically a draw, and halfmove 90 is not a rule that all quiet
moves are forbidden. Genuinely forced legal replies may still return instantly;
one move surviving a heuristic filter is not a forced chess reply.

The concrete regression is native opening 165, Black to move before
`83...Rf4`, with full history from the saved game. Tablebase evidence says
the position is drawn; `...Rg3` draws and `...Rf4` loses. Storm's static +88
classifier removes `...Rg3`. Four other tablebase drawing moves remain in
the filtered set, so this is both a bad exclusion and a decision-quality
problem, not proof that removing the filter alone fixes the game.

Assign actual claimable terminal draws zero and compare them with searched
alternatives. Preserve the defensive perpetual from site R22. Distinguish
true threefold, a second occurrence, and a claim possible by *any* intended
legal move before get_move. Maintain a canonical repetition key that excludes
an en-passant square unless an EP capture is legal, including pinned EP.

Make TT scores context-valid. A score dependent on a reversible history,
halfmove counter or cap distance must not be reused as an exact bound in a
different context. Build a correct reference using a reversible-history/count
signature plus rule context; hash moves can still be reused for ordering.
Optimize a cheaper cutoff guard only against differential tests. Adding only
the current position's repeat count or clearing TT each real move is insufficient.
Test cold/prewarmed/disabled TT on the same board with different histories,
rule-50 counters and cap distances, and interrupted-search bound validity.

## 3. Build a fast, calibrated positional evaluator

Keep exact incremental PeSTO as the base. Add small, separately switchable
feature blocks with an independent Python reference and integer native output:

1. **King danger and defensive coordination.** Pawn shelter and open/semi-open
   files near the king; enemy attacks into a bounded king zone; coordinated
   attackers and safe checking access, scaled by attacking material and queen
   presence. Defenders and safe king escape squares should matter. This should
   recognize the R23 attack before the h-file opens, and the quiet defences
   in R17. Avoid blanket punishment of every active endgame king.
2. **Pawn structure and useful activity.** Isolated/doubled pawns, blockers and
   pawn support; safe piece activity and rook files; central pawn breaks that
   release restricted pieces. Inspect R16's repeated missed `d4`, R18's
   coordination, and R20's `...e4`. A generic bonus for any pawn push would
   also reward R23's damaging `h4`; features must describe the position.
3. **Passed-pawn and rook-ending conversion.** Advancement with blockers,
   king stopping distance and tempo, support from king/rook, rook activity,
   and competing passers. Correctly reduce the value of an advanced pawn
   blocked by our own rook. The confirmed diagnostic is `50...Ra1` versus
   `...Ra3`: approximately 0.00 versus +4.36 for Black in the 5-million-node
   reference. Use opening 165's full sequence as a diagnostic,
   including its drawish phase, not as a permanently winning training label.

Cache pawn-only work with a pawn key. King-dependent terms need king squares
in the key or separate computation. Reuse existing attack primitives and
bounded king-zone calculations; do not generate all legal moves or rescan all
sliders for mobility at every leaf. Keep native and reference/fallback scores
consistent. Test colour symmetry, every special move and exact incremental
undo. Keep scores safely below mate bands.

**Fit the coefficients; do not merge the untuned r3 bundle.** Create a broad
offline corpus from legal public games and independent generated positions,
split by game/opening *before* fitting. Use an initial order of 20,000–50,000
positions, stratified across middlegames, attacks and endings, with frozen
validation partitions. Fit static corrections primarily on quiet/quiesced or
stability-screened positions. Keep transient tactical capture/mate swings in
search diagnostics rather than teaching a positional feature to explain them.
Independently produced engine labels are allowed as training data.
Robustly fit a regularized, tapered correction to the PeSTO
baseline, excluding mate scores and treating draw labels appropriately.
Record provenance, feature units, splits and validation residuals. This is a
starting dataset size, not a claim that it guarantees strength. Mine training
errors on the training partition; never tune on final match outcomes.

Keep each feature block independently selectable. Compare fixed-node decision
quality, native fixed-wall decision quality, then games. Aim initially for
roughly <=15% extra native search time on the same diagnostic workload; accept
more only if independently measured playing strength pays for it. Recalibrate
evaluation-dependent pruning and score-change thresholds rather than assuming
all old centipawn margins remain suitable. Ship original code and fitted
coefficients, never a runtime lookup database of reference engine answers or
a published network. A newly trained compact network is a later option if
the cheaper feature model plateaus, not a prerequisite for this first Odin.

## 4. Preserve tactical strength while recovering quiet defences

Keep Storm's verified LMR fail-high/full-depth/PV re-search and make/unmake
gates. Do not remove reductions globally or assume another search acronym is
the missing advantage. Build diagnostic switches for LMR, null move, reverse
futility, forward futility and SEE pruning so their effect can be isolated on
the retained roots at fixed nodes and fixed wall time.

Use those probes to determine why R17's `...Qg8` / `...Ke7` and R23's quiet
repair moves are not preferred. If a pruning family suppresses a saving
defence, add a narrowly justified danger/zugzwang guard and its regression;
do not exempt every quiet move. Add verified null-move fail-high handling in
vulnerable sparse rook/minor endings, with no fictitious repetition/cap edges.

Improve aspiration retries: widen only the failed side geometrically, order
the retry with the returned fail-high move, and preserve the last completed
exact iteration as fallback. Test equivalence to full-window fixed-depth
search and correct deadline interruption. After SEE is repaired, test ordering
good captures before strong quiet moves and losing captures afterward.

Retain the positive tactical controls in the reviews: native opening 174's
`17...Nf3+`, opening 175's attack, site R19's fast mating conversion, R20's
eventual passed-pawn promotion, and R22's defensive perpetual. Odin must gain
positional judgment without sanding away Storm's tactical strength.

## 5. Allocate time from measured uncertainty and useful completed work

Do this after the rule, search and evaluation interfaces are stable. Storm
already uses phase, game age, best-move stability, score changes and aspiration
failures. `SearchClock.root_effort` exists but is never supplied.

Record per-root-move nodes and bound type in reusable root arrays. Feed the
winning move's actual node share to the controller. Track exact completed
iterations, retry work, aborted work, initial/final soft target, hard allowance
and stop reason. Never treat a null-window second-best bound as an exact gap.
Maintain a bounded best/second-best comparison only where the search establishes
it. Keep telemetry compact enough for the site's first/last 4 KiB retention.

Use this evidence to reduce wasted aspiration work and avoid beginning an
iteration unlikely to finish. Reserve more useful decision time for complex
rook/queen endings; few pieces do not make pawn races easy. Evaluate changes
against the current policy on matched games and roots. The objective is better
decisions at the same clock, not a smaller final bank. R23 already spent
8.970 seconds on `28.Qe2`; a global budget increase is not the proposed fix.

## 6. Validate generalization and deliver an actual release

The old synthetic holdout contains underdeveloped/uncastled starts and hanging
pieces. It is a useful separate stress set, not Odin's main strength corpus.
The 82.5% Storm-v3 score remains historical; do not pool it with site results
or use v3 as the successor's only opponent.

Build realistic development starts covering e4/d4/flank openings, closed/open
centres, both/same/opposite castling, and queen/rook/minor endings. Keep starts
legal and screen obvious material/tactical imbalance with an independent
reference. Review actual development and king placement, not only PeSTO phase.
The present ten site games, all old matches and reference-labelled roots are
now known diagnostics. Keep separate fresh openings unseen during tuning.

Use small paired development screens and feature ablations first. Then declare
one fixed **40-opening-pair / 80-game native holdout** against the frozen
**rules-corrected Storm control** at
120 s + 0.5 s under the new pinned referee, with both colours per opening,
fresh processes, immutable candidate bytes and no changed stopping rule.
Require complete pairs, no Odin operational failures, a paired 95% score
lower bound above 50%, and a complete provenance/resource/referee audit.
If inconclusive, report it honestly and keep the candidate unpromoted; a
subsequent independent test needs a new declared plan. Do not repeatedly peek
and extend the same sample until it passes.

This primary gate must establish strength beyond the mandatory rule/buffer
repair. Also run a separate **16-pair / 32-game full-clock check against the
exact original Storm release**, using a predeclared subset of those openings,
and report its score separately. Require a positive score on this guard check;
do not claim statistically established superiority from that score alone.
Neither run may change the frozen Odin candidate or control. Include a
separate fixed challenge set/opponent family if available
to detect overfitting to Storm, keeping its evidence separate. Offline external
engines may act as analysis/sparring tools within the live rules; none belongs
in the submission. Do not claim a fixed-node handicap corresponds to a known
platform Elo or to beating the leading teams.

Native release gates must test the exact Linux-built archive: Python 3.12,
current package versions, one core, 2 GiB, no network, clean caches, one thread,
official import/protocol/deadline behavior and source-only packaging. Aim for
comfortable cold-init margin relative to the live 90 seconds; actual site
Storm imports were 37.7–45.7 seconds. Rerun only checks affected by new changes
or unresolved failures after a full gate passes.

Deliver `Odin-v5-linux-x86.zip`, its hash/manifest, the complete results and
limitations, and a promotion recommendation. Preserve the current official
the signer archive (not in git) until promotion is explicitly requested. Update the
handoff with measured outcomes and unfinished work. Do not upload for the user.
