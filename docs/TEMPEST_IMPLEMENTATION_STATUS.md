# Tempest implementation — 6 September 2026

**Tempest r1 is now outside git** as `agent.zip` and `Tempest-r1.zip`, SHA-256
`0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4`.
Odin v6 remains preserved as `Odin-v6.zip`. No site upload was performed.
Canonical source is **`tempest_exact/`**. `tempest/` is the rules-only fallback.

This is a conservative referee/endgame release, **not the hoped-for general
middlegame leap**. The neural pilot failed its held-out gate and is excluded.
The linear control improved average error but failed phase-tail guards and is
also excluded. Full details and current validation: `TEMPEST_R1_RELEASE.md`.

## Completed foundation

- Read the R&D report/specification and re-fetched the official contract/rules.
- Isolated the 12 v6 modules in `tempest/`; corrected the native fifty-move
  predicate and its qsearch/negamax triggers to 100. Search, fitted evaluation,
  clock, legal root filter and historical cycle heuristic remain unchanged.
- Pinned untouched current harness at `284724ab56cecb2a1a9a4e5769b4748adab4ed90`.
- Passed local compiled fifty 98/99/100, zeroing-resource, quiet mate, actual
  repetition, mate/stalemate precedence and 599/600 absolute-ply checks,
  plus six depth-three perft positions. Exact scripted referee games included.
- Linux archive `lab/odin/native_release/tempest-rules-r1/candidate-linux-x86.zip`:
  SHA-256 `843bc61c63fd5c30ab39d7ed5065f598203e6ae744579dacd8fa491f26e9eade`.
  Native gate PASS, structural cold import 32.703s, protocol cold import
  33.970s, extracted-source/resource/deadline gates passed. This is a fallback
  artifact, not an established playing-strength improvement or signer release.

The first remote gate invocation lacked the workspace import path and failed
before launching agents. The rerun used the module entrypoint and explicit
`PYTHONPATH`; its successful report is preserved. No match was discarded.

## New v6 site games

User attributes rounds 35 and 36 to Odin v6. Both are checkmate wins: White
against Rush hour (104 moves), Black against Dogwarts (53 moves). Version
attribution is the user's upload history; the PGNs contain no archive hash.
Full available histories were replayed legally under the updated referee.
There are 284 screened positions at 100k reference nodes and 12 selected
same-root unrestricted/played comparisons at 2M nodes each.

Important finite-reference comparisons:

| Game / decision | Played | Reference alternative | Own-side scores, best / played | Clock before move |
|---|---|---|---|---|
| Rush hour, 14.White | c5 | d5 | +1.15 / −0.39 | 109.13s |
| Rush hour, 17.White | Bb5 | cxb6 | +2.29 / 0.00 | 99.53s |
| Dogwarts, 29.Black | h3+ | Qc2+ | +3.24 / +1.51 | 53.53s |
| Dogwarts, 30.Black | Nxg3 | Kg7 | +2.66 / +0.38 | 48.33s |

These were wins with missed opportunities, not flawless demonstrations. The
early choices strengthen the case for evaluation/decision-quality work, but
do not alone identify its cause. Deeper analysis cleared multiple late
accusations: two Rush hour king moves and Dogwarts' queen capture remained
the reference choice. Forced-mate distance differences are not centipawn losses.

The Rush hour log reports mate scores and mostly depth-one/tiny-node searches
through a prolonged queen conversion. `SearchClock.should_start` stops on a
positive mate score. Removing that stop produced mixed wall-clock diagnostics;
the subsequent fixed-node comparison gave identical conversion lengths in all
four cases. **The mate-stop rule remains unchanged.** No cached-mate bug was
established. Original exact KQK/KRK tables address conversion directly.
Minimum served clock was 897ms in Rush hour and 3658ms in Dogwarts; these
are not measured pre-increment deadline headroom.

Evidence and scripts: `lab/tempest_build/day3-v6/` and
`lab/tempest_build/review_v6_games.py`. Reference analysis is offline Stockfish
19 with cleared hash, equal budgets for same-root comparisons, completed exact
iterations and retained full available history. It is not game-theoretic truth.

## Decision-data pipeline

`lab/tempest_build/prepare_data.py` freezes whole-family partitions before
labels. After exclusions and correlation caps, the existing human PGNs yielded
**1,131 roots across 578 unused opening families**, not the proposed 2,000:
906 train, 131 validation, 94 test roots; 650 high-material, 370 middlegame,
111 endgame. This first tranche remains short of the desired endgame coverage
and does not yet contain new self-play. Do not silently describe it as 2,000
roots or 20k independent training examples.

The offline sampler stores paths and bitboards in an expanded lab-only search
counter buffer, rejects null-search paths, reconstructs legal leaves and checks
their static scores. It records up to eight quiet and two guard states per root.
Deterministic reservoir selection over visits is followed by deduplication and
per-root caps; resulting selection is not claimed to be an unbiased sample of
all chess positions. It does not label static leaf scores as exact root scores.

Thirty controls match uninstrumented fallback move, score, depth and node
count exactly. A–B–A determinism and path/evaluation reconstruction passed.
`data/sampler-identity.json` records the control gate. Full sampling produced
5,754 distinct legal states: 3,495 quiet and 2,259 guard states. Four CPU-pinned
workers labelled every state at 200k reference nodes with full stored history.
No cross-split transposed leaf positions were found. Mate/terminal/extreme
targets were excluded from this scalar pilot, leaving 4,159 train, 684
validation and 445 test examples.

The proposed network is original eight-king-bucket 6144×32, two perspective
accumulators with antisymmetric clipped activations and tapered outputs.
The pilot retains v6's evaluator as its base. Scalar training is an explicitly
recorded first ablation; move-ranking, integer runtime, integrated inference,
current-rule paired games and fresh full-clock promotion remain separate gates.

## Completed pilot outcome

The selected original network improved training MAE from 274.32 to 229.85 cp,
but **worsened unseen-family test MAE from 267.16 to 272.14 cp**, with a large
middlegame tail regression. Six predeclared seed/regularization trials were
reported; the test set selected none of them. The network does not ship.

The linear control improved test MAE to 255.45 cp (11.71 cp improvement).
Equal-family paired bootstrap was positive (approximately +2.1 to +30.0 cp),
but endgame p90 increased from 514 to 528.76 cp and quiet-position p90 from
411 to 420.64 cp. This merits further data work, not an automatic deployment.
The high scalar errors reflect actual search-state labels, including guard
states; they are not directly comparable to the previous quiet 97 cp dataset.

The first training invocation caught an encoding-symmetry assertion before
fitting: feature multisets were equivalent but enumerated in different orders.
Sorting indices made both perspectives use deterministic summation order.
The setup-only plan was preserved; no candidate result was discarded.

## New round 37: Neural Gambit

This is another v6 game, a White loss by mate on move 43. Earlier round 28 was
a Storm win from a different opening. Do not infer opponent-version changes
or engine regression from those two results. Storm's win also contained major
missed opportunities, including 26.Rc1 instead of Ne5, which the prior Odin
review had already diagnosed.

At 21.c5, the new same-root reference preferred Rcd1 (−0.96 vs −2.51).
At 23.Qc3 it preferred Kf1 (−3.19 vs −5.04). At 24.Qxa5 it preferred Qc2
(−4.99 vs −6.57). These are finite 2M-node estimates. At 24.Qxa5, v6's own
log still reported +0.63 after 9,432,064 nodes and 11.759 seconds, with 71.745
seconds available before the move. Simply granting another few seconds is
not an evidence-backed remedy.

Reconstructed probes at 200k/1M nodes and 1.5 seconds reproduced c5 and Qxa5.
Removing LMR or futility pruning did not repair either choice. Those changes
also chose Qc5 rather than Kf1 at the intermediate root; it has not been
established as a better defense. Do not label the unexplained same-move
reference gap for 30.Qf3+ as a blunder: unrestricted and forced searches both
selected Qf3+, so the difference is reference instability, not a move choice.

The new game remains diagnostic data and was not inserted into training or
used to select the already-frozen test split. R&D still needs to distinguish
king-safety representation from selective horizons in the critical subtree.

A further opponent-side probe after 24.Qxa5 sharpens that diagnosis. Odin v6
chooses ...Qh2+ at 200k nodes, 1M nodes and 1.5 seconds, with scores of −1.17,
−0.94 and −0.99 from Black's perspective. Separate forced 2M-node reference
searches rate the actual ...f4 at +8.79 for Black and ...Qh2+ at +8.71.
Both continuations win; the tiny reference difference does not establish that
the different UCI is a mistake. The engine can find a strong attack once
given Black's position, yet substantially undervalues it even then. This
supports investigating defensive valuation and continuation assessment,
without claiming that evaluation rather than search horizon is proven causal.
Evidence: `day3-v6/round37-opponent-probes.jsonl` and
`day3-v6/round37-opponent-forced-reference.json` under `lab/tempest_build/`.

The released Tempest r1 also completed its two additional full-clock smoke
games: two draws, 246 audited legal plies, zero operational failures. These
are deployment checks, not evidence of a general strength leap. See
`TEMPEST_R1_RELEASE.md` and the native stage's `fullclock-audit.json`.
