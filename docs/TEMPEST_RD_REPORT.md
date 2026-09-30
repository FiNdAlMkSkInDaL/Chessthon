# Tempest R&D report — 6 September 2026

## Decision

Keep Odin v6's search architecture. The experiments do **not** establish a stronger Tempest engine, and they do not support removing a pruning family wholesale, adding the tested evaluation terms, deploying the old small network, or simply spending more time everywhere. The highest-value next programme is to improve the information supplied to the existing search: collect representative search leaves and competing continuations, obtain more stable labels, and compare an original compact residual evaluator against a strong linear control. This is a conditional build recommendation, not a claim that neural evaluation has won a test.

There is also a new, mandatory rules dependency. The live starter changed after the v6 release test. Its exact commit is **284724ab56cecb2a1a9a4e5769b4748adab4ed90**, whose parent is the old pinned **91f70e54be07e1bf56311962044a08b822c3af50**. It now checks `board.outcome()`, then actual `board.is_repetition(3)` and `board.is_fifty_moves()`. It no longer uses `outcome(claim_draw=True)` to terminate because an intended next move could complete a claim. [Official change](https://github.com/advitrocks9/aichessathon-starter/commit/284724ab56cecb2a1a9a4e5769b4748adab4ed90).

The implementation specification is [TEMPEST_BUILD_SPEC.md](TEMPEST_BUILD_SPEC.md). Numerical search tables and machine-readable results are [tables.md](../lab/tempest/tables.md) and [summary.json](../lab/tempest/summary.json). These are discovery measurements, not Elo estimates.

## Baseline, scope and preservation

the signer archive (not in git) and `Odin-v6.zip` were both verified against SHA-256 `cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647`. `odin_v6/` is the source of record; `odin_submission/` is not the baseline. All release files, old reports, pinned harness files, stop markers and archives were preserved. No promotion, upload, purchase, message to another person or VPS service change occurred.

The prior 112-game result remains **30W/69D/13L, 57.59%, paired 95% interval 52.23–62.95%, zero operational failures** under its recorded referee. Its repaired Linux/local audits are authoritative; the original automatic import error remains preserved. It is not evidence from an untouched current-rules holdout. Replaying all **14,743 plies** against the new terminal predicate shows that **all 63 threefold/fifty-move draws would still be live at their recorded final position**. This does not turn them into wins or losses, invalidate their original result, or tell us what the next move would have been.

The Day 3 folder still contains only rounds 31–34. They are the user's reported v5 upload, with no archive hash embedded in the PGNs. New public pages reveal further rounds, but public team names and cumulative records do not identify a submission. Do not call those v6 site results. See [identity.json](../lab/tempest/identity.json) for the re-enumerated folders and immutable source hashes.

The baseline already has PVS, LMR, null move, reverse/forward futility, IIR, SEE, check extensions, TT, fitted 24-feature evaluation, and adaptive time allocation. The native evaluator rescans positional geometry and adds a tapered correction to PeSTO. `SearchClock` already reacts to move stability, aspiration failures, score changes and iteration growth. It accepts root effort, but the current driver does not supply it. `history.filter_root_moves()` returns all legal moves; its old claim-scanning helpers are inactive. Search path repetition remains a cycle heuristic, distinct from exact referee threefold.

## Live contract and newly verified rule behavior

HTTP copies of the contract, rules, rendered docs, leaderboard and relevant starter source are saved with retrieval timestamps, headers and hashes in [public/fetches.jsonl](../lab/tempest/public/fetches.jsonl). The web tool failed on some Markdown/team URLs; ordinary public HTTP succeeded. The unchanged deployment limits are Python 3.12, one EPYC 9V74 core, 2 GB, no network/GPU, 90-second import, 120 seconds plus 0.5 seconds after the move, one persistent process suspended on the opponent's turn, readable source, 50 MB uncompressed, and 256 MB temporary storage. The 600-ply cap includes the opening. [Official docs](https://aichessathon.com/docs).

Original trained weights and Numba JIT are permitted. Published networks, third-party engines/translations and shipped engine-answer lookup databases are prohibited. Books and tablebases are explicitly permitted as data; the earlier development cuts were not competition bans. Their provenance, size and utility still need measurement. [Official submission rules](https://aichessathon.com/docs#submissions).

[rule-probe.json](../lab/tempest/rule-probe.json) contains five passing cases: intended versus actual third occurrence, halfmove 99 versus 100, and mate precedence. The exact source difference is [referee-diff.patch](../lab/tempest/referee-diff.patch). All 24 acquired games replay legally and have no premature termination under the new predicate. Three appeared to run past a claim boundary under the old predicate; the new source explains all three. Preserve [public-audit.json](../lab/tempest/public-audit.json) as the explicitly legacy-predicate first audit and use `rule-probe.json` for the current-rule interpretation.

## Opponent evidence

### Sample and freshness

Acquired **24 distinct completed PGNs** through public HTML download links across ms, AI Fellows, AlphaFish, Capablanca, FuzzyBot and adashima, including crossover games. Selection sought recent white/black games and wins/draws/losses, with at most five selections per team and game-ID deduplication. It is deliberately diverse, not a random sample. A second team-page retrieval retained all 24 as completed non-void results. Void rows remain in the team inventory but were not counted. Sources and original results are in [public/games.json](../lab/tempest/public/games.json) and [public/team-inventory.json](../lab/tempest/public/team-inventory.json).

The initial leaderboard was through round 34 while team pages already included round 35 and newer page states. Do not reconcile these by inventing a common rating snapshot. The initially quoted AI Fellows #12 and ms #14 are dated leaderboard observations only. The acquired sample records below are **sample counts**, not current team records:

| Team / PGN identity | Appearances in the 24 games | W–D–L in sample | Median final clock | Median of game-level early / late move-time medians |
|---|---:|---|---:|---|
| ms | 5 | 2–1–2 | 7.467 s | 3.799 / 0.659 s |
| AI Fellows | 5 | 2–2–1 | 2.304 s | 4.425 / 0.594 s |
| AlphaFish / Emile Andrieu | 5 | 3–1–1 | 31.797 s | 3.140 / 0.920 s |
| Capablanca / THE ROOOOOKKK!!!! | 4 | 1–1–2 | 30.933 s | 2.442 / 0.949 s |
| FuzzyBot | 5 | 2–2–1 | 4.448 s | 3.096 / 0.639 s |
| adashima | 5 | 3–0–2 | 20.450 s | 3.015 / 0.858 s |

Early means the first 40 served-game plies; late means ply 80 onward. Clock comments exist for every recorded move; differencing a side's consecutive remaining clocks with the increment produced no negative elapsed times. These are observable timing patterns, not measurements of opponent nodes, depth, CPU use or allocation policy. Forced moves, material reduction, winning positions and clock depletion are alternative explanations for faster late play. AlphaFish's banked time also refutes a universal claim that strong engines must spend nearly everything.

Ten games across six whole named opening families were reserved from reference/engine analysis in the initial split. The remaining **14 games supplied 1,330 first-100-ply move comparisons**, at 50k nodes unrestricted plus 50k restricted to the played move. We excluded forced moves, mate scores and heavily decided positions when inspecting balanced-position error rates. Colour, material, clock and opponent identity are retained in every row. These controls reduce obvious confounding, but tiny per-team game counts cannot normalize opponent quality enough for a ranking.

The shallow screen is only a locator. Same chosen move with a different restricted-search score is reference instability, not a move error. Nineteen earliest/later consequential divergences were deepened at **2M nodes per unrestricted and played-move search**, retaining complete history. See [public-deep.jsonl](../lab/tempest/public-deep.jsonl). Several alleged errors disappeared, including AlphaFish's Kxg2; Make_no_mistakes' c5 was not supported as a mistake. Negative reference regret is preserved, not silently rewritten into an accusation.

### What they demonstrably do, and what remains unidentified

**ms — observed:** exploits weak defensive placement and plays active pawn counterplay. Against our v5, 12.Rae1 costs approximately 72 cp relative to Nb3 at the repeated 2M same-root comparison. Our later Qg4 increases an already serious defensive deficit. The failure starts with substantial time left. In a different game, ms itself plays 17...Ne4 where 17...d4 is about 150 cp better at the deeper reference. Therefore neither perfect tactical calculation nor uniformly superior pawn-break judgment is supported. **Inferred:** our defense and evaluation of counterplay are more useful targets than a bot specialized against ms. **Not identifiable:** its evaluator or pruning implementation.

**AI Fellows — observed:** turns our 10...Be6 into a lasting advantage; Bd7 is about 152 cp better for us at the repeated deep check. Its queenside passers and coordinated pieces in the later position are concretely dangerous. It also holds an insufficient-material draw against AlphaFish after a long rook ending, and plays a costly e4 in the Two Knights game against checkers (about 176 cp at the deeper check). **Inferred:** robust evaluation of the opponent's resources, simplification and conversion is a plausible general weakness in ours. **Not identifiable:** whether that comes from a network, classical terms, search coverage or a larger effective node budget.

**AlphaFish — observed:** wins from both colours in the sample, activates pieces in tactical middlegames, and uses active rook/king play in the drawn AI Fellows ending. Our broad v6 probes reproduce several of its moves, including Rxb2, Kh8, Qb1+ and Ne2+, already at 200k nodes. Its shallow apparent Kxg2 error disappears at 2M. A loss and a draw are retained in the sample. **Not established:** a distinct algorithmic advantage from these games, or that every attractive attacking move is inaccessible to v6.

**Capablanca — observed:** both attacking/conversion play and fallible defensive decisions; the French game includes a reference preference for exchanging on c1 instead of Qd8. **FuzzyBot — observed:** coherent development and simplification in the London draw, plus a win over ms in the reserved Petroff game. The reserved game's moves were not used to tune or evaluate candidates. V6 matches Bc4 and Nc3 in the inspected London roots. **adashima — observed:** finds concrete resources against our overextended pawns; our 21.e7 is substantially worse than f6. Other sampled games contain missed resources by adashima too. These are useful style guards, not downloadable opponent engines.

The exact broader same-root comparisons are in `summary.json` under `opponent_roots`: 39 non-mate comparisons, 19 identical choices at 200k v6 nodes. Additional [opponent-critical.json](../lab/tempest/opponent-critical.json) positions reconstruct **12 opposing turns immediately before/after our known errors**, with 200k/1M-node and 1.5-second v6 probes. V6 reproduces **6/12, 7/12 and 6/12** actual choices respectively. It reproduces all four sampled adashima resources, including ...Qb8; some ms alternatives chosen by v6 receive better finite reference scores than ms's move. The final summary is [opponent-critical-summary.json](../lab/tempest/opponent-critical-summary.json). This directly tests exploitation rather than attributing an opponent's move to secret technology. A reproduced strong move indicates a defensive/sequence problem in our game, not an inability to generate that attacking move.

Three apparent broad-sample advantages were deepened again at 2M per unrestricted/actual/v6 search in [opponent-advantages.jsonl](../lab/tempest/opponent-advantages.jsonl). Adashima's **14...bxc5** scores about 72 cp better for Black than v6's 200k-node **...dxc5**, retaining the central d-pawn; this is a concrete near-balanced structural choice worth diagnosing. Ms's Qc1 advantage shrinks to 19 cp. Its Rf1 scores 141 cp above Bf2, but both reference scores are already strongly winning and the unrestricted/forced estimates disagree. Do not treat that centipawn difference as a demonstrated conversion-rate advantage. These comparisons use the same reference budget for both moves; they do not equalize the unknown opponent node budget or reproduce contest hardware.

Overall, the evidence supports **better practical exploitation of our defensive mistakes in these games**. It does not establish that the named rivals use neural evaluation, a sophisticated importance model, more nodes, or an architectural technique we lack. The broad roots frequently agree. Teaching the next engine the named opponents' moves would miss the point.

## Experiments and causal conclusions

### Corpus and controls

[corpus-v1.json](../lab/tempest/corpus-v1.json) has 84 deduplicated positions: eight known Day 3 roots, 72 scheduled public-game roots, and four original constructed controls. The initial split leaves 30 positions in ten public games unsearched; 54 discovery roots include routine good play and endings. The focus is 24 roots, balanced between the known/constructed controls and public sources. Entire named opening families share a split. Three reserved positions share an old starting FEN, so these reservations are **not certified fresh promotion families**. The separate `fresh-confirmation/` set fixes that: 12 balanced openings, four each e4/d4/flank, excluding previous selected development/release families and known game transpositions, with no v6/candidate search. Further final-promotion families must still be frozen separately.

Every native prototype derives from v6, with source hashes recorded. The baseline prototype's core underwent line-ending normalization only; all 12 module ASTs match released v6. Drivers reconstruct only historically available served/own-move history, reset all native module arrays and history per root, retain full completed-iteration traces, require native readiness/signature stability, and pass A–B–A isolation. Direct root calls bypass `get_move`'s clock/firewall wrapper; every returned UCI is independently legal. These are search diagnostics, not fresh-agent protocol tests or persistent-TT game reproductions.

All timing was on the Windows ARM Python 3.12 environment, with workers affined to distinct cores and thread counts pinned. Native searches used roughly 0.6 GB resident memory per process. No native Linux timing or promotion test was performed. No configured SSH alias was present, and the scoped prior project session did not yield an established connection target; no username guessing occurred. The previous v6 Linux numbers remain historical measurements, not measurements of these prototypes.

### Six search/evaluation variants

The predeclared variants are baseline, LMR off, reverse+forward futility off, SEE pruning off (main search and qsearch SEE; qsearch delta retained), null move off, and PeSTO-only evaluation. Each receives 24 roots × three budgets: 200k nodes, 1M nodes and 1500 ms. Baseline also receives 30 additional 200k-node roots. All completed variants, including negative results, appear in [tables.md](../lab/tempest/tables.md).

The quality metric uses **the same 1M-node restricted reference budget for each compared move**, measuring the deficit to the best measured candidate at that root. It is finite candidate-set regret, not exhaustive minimax loss. Mate references are separated from centipawn averages. Different variants nominate the pool, so its absolute level is selected data; paired differences are the useful diagnostic. Missing references are reported by the validation script and must be zero at handoff.

None of the blanket pruning removals establishes a general decision-quality improvement sufficient to compensate for lower completed depth and sometimes worse short-wall decisions. This does not prove each individual pruning condition is correct. The futility experiment groups RFP and quiet futility; the SEE experiment groups main and qsearch SEE. A localized gain would need a second ablation to separate those members. IIR and continuation history were not re-presented as new ideas: their earlier extensive screens already failed to establish improvement.

At 1M nodes, the 22 non-mate focus roots have mean candidate-set regret **51.0 cp for v6, 50.9 LMR-off, 51.3 futility-off, 54.7 SEE-off, 51.0 null-off and 40.6 PeSTO-only**. At 1.5 seconds, PeSTO-only improves the paired mean by 12.5 cp, with four improvements of at least 30 cp and no regressions of that size. This is a positive selected-root result, especially recovery of Bd7, and motivated one **12-game / six-pair development screen at 100 ms per move**.

**The follow-up rejected PeSTO-only: 4W/1D/7L, 4.5/12 points (37.5%).** All **1,352 legal plies** were replayed under the new terminal rules; worker identities, A–B–A resets and complete reversed-colour pairs passed. The predeclared 60% threshold for a later confirmation was not met. [Match plan and audit](../lab/tempest/match/summary.json). This small selected development sample is not proof of a precise Elo loss, but it supplies no reason to remove the fitted evaluator. It also shows why a regression-root improvement must not become a release claim. The clock is 100 ms search allowance per move, not 120+0.5; maximum observed wrapper wall time was 196.6 ms, so no full-clock flag-rate claim is made.

### More budget and forced alternatives

The eight own roots also received **4M-node v6 searches**, and **1M-node searches restricted to each of the played and reference alternatives** (25 searches total). Single-root early stopping was explicitly disabled in the offline forced driver. Independent restricted searches do not have equal depth and do not recreate unrestricted root ordering.

| Position | V6 at 4M nodes | Selected forced-root v6 scores at 1M nodes, side to move |
|---|---|---|
| ms, 12.White | Rae1 | Rae1 +1; Nb3 -13 |
| ms, 17.White | Be3 | Qg4 -83; Kh2 -92 |
| AI Fellows, 10.Black | Be6 | Be6 -40; Bd7 -33 |
| AI Fellows, 24.Black | Kh7 | Bxe4 -174; Kh7 -170 |
| adashima, 20.White | exf5 | exf5 -34; c5 -62; e7 -62 |
| adashima, 21.White | e7 | e7 -75; f6 -137 |

**Observed:** additional search repairs Kh7 and changes the 17.White choice, but repeats four other known errors. Forced alternatives remain misranked in several cases. **Inference:** root move order alone is insufficient; the problem survives in subtree search/evaluation. **Not isolated:** static evaluation versus horizon/selectivity within those subtrees. The result does not license calling a specific coefficient wrong. Reference-PV static curves are retained as diagnostics, not presented as native PVs or causal proof.

The 200k→1M budget curve has 15/22 identical choices, one improvement and one regression of at least 30 cp. Do not equate depth or node count with monotonic move quality. Full recorded-clock v5/v6 probes already exist, but their missing historical TT and different hardware remain limitations. No new clock multiplier is justified without persistent-state replay and evidence of where marginal time helps.

### Evaluation/data interventions

An original 12-relation residual model adds blocked/support/connected passer information, safe path access, king distances, undefended/attacked pieces, restricted minors, nearby open king files, pawn contact and supported knight outposts. It keeps v6's 24 features fixed. Four Huber/ridge settings are chosen on the original training-family inner split, then refitted on 4,247 examples. The 1,354 outer examples were already reused historically and remain descriptive.

| Model on the same reused outer set | MAE cp |
|---|---:|
| V6 24-feature evaluator | 97.244 |
| New relations, float | 96.830 |
| New relations, rounded int32 | 97.003 |
| Prior best small original network, historical same-label result | approximately 96.81 |

The rounded model worsens p90 absolute error from 249.7 to 254.0 cp. Quantization changes its correction by 2.69 cp on average. No search integration or match was justified. Its float gain is similar to the old network's gain and does not demonstrate that a larger model is the missing answer. [Plan, coefficients, matrix and results](../lab/tempest/eval-relations/result.json).

The 5,601 quiet rows have only **363 low-material-phase examples**, including 101 validation examples; original broad labels called many more positions 'ending'. Material phase and a dataset's narrative bucket are not interchangeable. Training/validation opening keys do not overlap, but validation has been repeatedly inspected. Quiet filtering excludes many unstable and imbalanced search states that an evaluator actually encounters.

A deterministic audit reanalysed **120 old labels, 40 per material-phase stratum, at 1M nodes**. Median absolute change was 13 cp, mean 29.2 cp; 17/120 changed by at least 50 cp and 7/120 by at least 100 cp. On those same 120 examples, v6's MAE rises from 101.9 against the old labels to 124.85 against the deeper labels; the new relation model gives 100.82 and 124.32 respectively. Hash size and missing full history also differ, so this is reference instability, not a pure estimate of node-depth noise. It supports selective relabeling and held-out decision tests, not the claim that all evaluation error is label noise.

### Incremental representation feasibility

An original Numba accumulator prototype uses our own historical 768×16 int16 weights with int32 accumulation. It passes **2,999 forward/reverse state checks**, covering 32 castles, nine en-passant captures and 29 promotions. Two repeated runs over 599,800 transitions take approximately **0.267 s incremental versus 0.474 s full refresh**, about **1.78×** within that isolated loop. The embedding is 24,576 bytes; two 16-unit int32 accumulator stacks at 96 plies require 12,288 bytes.

The benchmark excludes Python board-difference extraction, complete inference and integrated make/unmake/search costs. It is not an engine speedup. It establishes that original integer state updates are feasible; it does not validate a trained replacement evaluator, a 32-unit king-conditioned model, or Linux import/runtime costs. [accumulator-result.json](../lab/tempest/accumulator-result.json).

## Research synthesis and competing hypotheses

The NNUE principle is useful because only a few piece inputs change per move; integer accumulators can avoid recomputing a sparse first layer. King conditioning makes king moves require refreshes. This is a concept to implement originally, not permission to port another engine's code or weights. [Official technical explanation](https://official-stockfish.github.io/docs/nnue-pytorch-wiki/docs/nnue.html).

Lai's Giraffe work distinguishes root-position and internal-search-node training distributions and studies learned evaluation and selective search separately. Its data scale and search comparisons are substantially different from ours; its gains do not transfer numerically. It motivates sampling actual search states and testing representation against a linear control. [Primary thesis](https://arxiv.org/html/1509.01549). TDLeaf similarly connects learning to minimax leaves rather than only game roots; adopting its full self-play algorithm is unnecessary for the first supervised residual experiment. [Baxter, Tridgell and Weaver](https://arxiv.org/abs/cs/9901001).

| Hypothesis | Evidence / alternative | Smallest next discriminating test | Falsification / ship gate |
|---|---|---|---|
| Leaf representation/data limits decisions | Forced bad continuations remain preferred; relation/network gains on old labels are tiny. Alternative: deeper selective subtrees remain wrong. | Label sampled v6 quiet leaves and candidate-pair leaves; compare linear and king-conditioned residuals on untouched families, then equal-wall roots. | No clear pair-ranking/held-out gain, or search cost erases it: retain v6 evaluation. |
| A pruning family suppresses resources | Some move changes occur, but blanket removals do not yield a robust gain. Alternative: useful pruning permits deeper coverage. | Instrument reduced/pruned paths only around generalized flagged node classes; toggle one condition. | No equal-wall gain on unrelated roots and cheap paired games: reject. |
| Time goes to the wrong decisions | 4M repairs some choices but repeats others; budget gains are not monotonic. Alternative: wrong ranking persists at any practical budget. | Persistent-TT replay; estimate marginal improvement by observable uncertainty features, with a fixed total game budget. | Increased later losses/flags or no held-out benefit: keep clock. |
| Draw policy/endgames discard wins | New referee changes exact boundaries; 41/112 old games visit four-or-fewer pieces. Alternative: many repetitions/endings are sound draws. | Correct exact terminal semantics first; label a balanced sample of conversion/escape positions and measure useful tablebase coverage. | No expected-score gain across stronger/weaker guards: no contempt or broad draw aversion. |
| Replace alpha-beta with policy/MCTS or a large net | No positive contest-specific prototype; existing reliable search already finds many opponent moves. | Would require an original equal-wall prototype and much stronger data before implementation. | Present evidence fails this gate; do not replace search. |

## Ranked opportunities and handoff

1. **Search-leaf data and compact original residual evaluation.** Highest potential competitive value, moderate evidence that the current data/decision pipeline is limiting, high effort, uncertain strength gain. Target less than 10% integrated search throughput loss; no runtime framework imports. A data/representation experiment comes before deployment integration.
2. **Localized verification and coverage instrumentation.** Medium potential, weaker positive evidence, medium effort, potentially substantial node cost. Preserve current selective search and identify a condition with repeatable benefit. Blanket removals are rejected; don't turn the current corpus into a move-answer test.
3. **Measured state reuse and time allocation.** Medium potential, strong feasibility evidence for integer updates but weak evidence for a new clock, medium effort. Accumulators can fund a better evaluator; uncertainty-driven extra search needs marginal-benefit evidence. The two should not be conflated.

Rule alignment is a mandatory dependency, not an Elo opportunity ranked from these experiments. PeSTO-only earned a small development game screen because its selected-root improvement was stronger than the pruning results; it has not been promoted. The next agent should build the narrow architecture in the specification, keep a corrected-v6 fallback, and run the staged paired/current-referee tests before any promotion. There is no supported promise of a leaderboard leap.
