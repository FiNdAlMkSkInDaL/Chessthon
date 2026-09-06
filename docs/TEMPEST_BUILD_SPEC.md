# Tempest implementation specification — 6 September 2026

## Recommended architecture and fallback

**Recommended:** Odin v6's existing one-core Numba alpha-beta/PVS search, move generation, TT and clock, with current referee semantics and a separately gated original **king-conditioned sparse residual evaluator** trained on search-relevant data. Build its data/measurement interface first. The R&D run did not establish a winning evaluator or justify removing search features; no experimental coefficients or old network weights are approved for deployment.

**Fallback:** isolated copy of v6 with only the verified current-rule terminal correction and its associated tests. Retain the 24-feature evaluator and search settings. Test this fallback against exact released v6 under the new referee; do not overwrite released sources. If even the rule-corrected build is not ready, preserve the current archive rather than package an unfinished model.

PeSTO-only did improve selected-root reference regret, but its executed 12-game/6-pair development screen against released v6 scored **4W/1D/7L (37.5%)**, with 1,352 legal plies audited. It failed the predeclared follow-up threshold. This is why the fallback retains the fitted evaluation despite the attractive root ablation.

Baseline archive SHA-256: `cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647`. Read `odin_v6/`, not `odin_submission/`. The old release's 112 games are used discovery data and use the old claim-by-intended-move rule. All 63 of its repetition/fifty draws are still live at their recorded end under the new source; no counterfactual outcome has been assigned.

## 1. Isolate and correct the rule dependency

Create `tempest/` by copying the 12 source modules from `odin_v6/`. Record source/member hashes before editing. Stage an untouched official harness pinned to **284724ab56cecb2a1a9a4e5769b4748adab4ed90**, in a new directory. Preserve the old harness and finalizers. The exact changed file and five predicate fixtures are in `lab/tempest/public/referee-284724ab56cecb2a1a9a4e5769b4748adab4ed90.py` and `lab/tempest/rule-probe.json`.

In `tempest/core_nb.py`:

- Replace the historical `fifty_claim_nb` behavior with `nlegal > 0 and halfmove_clock >= 100`. Remove its scan for a quiet move at halfmove 99. In both `qsearch_nb` and `negamax_nb`, use 100 as the trigger for terminal fifty-move handling. Preserve checkmate/stalemate precedence, cap handling and legal evasions.
- Retain the existing search-path cycle heuristic initially, explicitly labelled as a heuristic. It is not exact referee threefold. Do not globally reinterpret one previous key as a forced referee draw; separating search cycles from real-game repetition requires a distinct ablation. Do not reintroduce `filter_root_moves`' old winning/zeroing exclusions.
- Keep the 600 absolute-ply cap and cap-sensitive TT identity. No 300-ply material mode. Review comments and tests that still describe the obsolete intended-move claim; avoid changing dormant code just to tidy it.

In `history.py`, preserve served-position/own-push observation, full game state, and the all-legal root filter. In the lab, update new reference/validator terminal predicates to match the new pinned harness. Preserve historical audit helpers for reproduction; don't mutate frozen plans to make old draws pass a new rule.

Required focused tests: halfmove 98/99/100; a zeroing escape; quiet mate at the boundary; actual third repetition versus a legal move that would make the third; castling/EP-sensitive keys; mate/stalemate precedence; absolute ply 599/600 including a non-startpos FEN. Run against the untouched new referee using scripted agents. The R&D predicate fixtures passed; **an integrated native fallback build has not yet been tested**.

## 2. Build the decision-data interface before a model

Add offline code under `lab/tempest_build/`; it must never be packaged. Suggested modules and contracts:

| File / function | Output / required invariant |
|---|---|
| `sample_search.py::collect_roots` | Versioned FEN + full available history + side + game/family ID + clock + source hashes; no future-state leakage. |
| `sample_search.py::collect_leaves` | Deterministic reservoir of quiet evaluation leaves plus unstable/imbalanced guard states from actual v6 search. Include root ID, leaf path, phase, native score/bound and selection probability. |
| `label_pairs.py::label_root_pair` | Same-root finite reference values for competing moves at equal budgets, actual nodes, depth, bound status, PV, complete history and reference binary hash. |
| `label_pairs.py::label_leaf` | Independent deeper leaf label and stability result; terminal/mate targets kept separate. |
| `split_data.py::freeze_splits` | Whole source-game and transposed opening-family groups; no duplicate position across train/validation/test; manifest and used-data registry. |
| `fit_linear.py`, `fit_residual.py` | Identical examples, labels, weighting, splits and candidate-pair ranking evaluation. |
| `export_weights.py::quantize` | Dtypes, scale factors, bounds, checksum, symmetry tests and float/integer disagreement. No third-party weights. |

Instrument root comparisons to distinguish exact scores from bounds; retain completed iterations only. A top-two margin inferred from fail-low PVS scores is not an exact margin. Optional counters: qnodes, evaluation calls, TT hits/cutoffs, LMR attempts/re-searches, RFP cuts, null attempts/cuts, quiet/SEE skips and per-root nodes. First prove instrumented A–B–A and equal-node identity against uninstrumented v6 on routine and difficult roots. Limit any leaf sampler to an offline build; per-node Python callbacks are forbidden in timed search.

### Data generation, bounded first tranche

Start with **2,000 root decisions** from unused human opening families and original v6 self-play trajectories, stratified by material phase, with a mix of roughly equal, defending and converting positions. This count and mixture are proposed budgets, not completed R&D data. Exclude all known Day 3, public diagnostic, old screening and old 112-game families. Do not train against the reserved confirmation/final games.

For each root, sample up to eight quiet leaves and two unstable guard states, deduplicating transpositions and limiting correlated leaves from one root. Candidate root moves are the v6 choice, a reference alternative, and at most one decision disagreement from a selective-search diagnostic. Store the path; a raw leaf FEN discards useful repetition context. The first tranche is at most ~20k states; scale toward 100k only after the small pilot demonstrates an improving learning curve. Do not promise that ~20k states can identify a ~200k-parameter model reliably.

Use 200k-node labels for broad screening. Deepen a predeclared mixture of random control labels and disagreement/unstable labels to 1M; use 4M for unresolved high-value pairs. Record the sampling mechanism so disagreement cases do not silently replace broad coverage. Cap one offline reference worker per available core; existing VPS maximum two active CPU workers and measured memory headroom. A single 4 GB VPS is not a training farm.

Reference labeling gates: no unresolved score bounds; record mate separately; compare consecutive exact iterations and a larger-budget recheck on a random subset. For candidate pairs, do not penalize the same UCI because unrestricted/restricted scores differ. Where a deeper reference changes its preferred move or restricted search finds a better result than unrestricted, retain an ambiguity interval or down-weight the pair. Never save an engine-answer database inside the submission.

The R&D label audit found 17/120 changes of at least 50 cp and 7/120 of at least 100 cp when deepened, with history/hash caveats. It also found only 363/5601 existing quiet rows in low material phase. Add examples because they cover actual search states and decision transitions, not merely to increase row count.

## 3. Model definitions and controls

### Strong simple control

Retain PeSTO and the 24 v6 features as a fixed base. Fit a tapered Huber/ridge residual using the 12 precisely defined relations in `lab/tempest/eval_experiment.py::extract`. That file, not an informal feature name, defines the reference behavior. It includes blocked/supported/connected passers, attack/defense relations, restricted minor mobility and king-file exposure. The completed pilot achieved only 97.003 versus 97.244 cp validation MAE and worsened the p90 tail; **do not ship those coefficients**. Refit on the new data, and compare it on the same candidate pairs as the network.

### Original sparse residual candidate — proposed, not measured

Use eight king buckets per perspective: four adjacent-file groups multiplied by two relative-rank groups. Orient each perspective with its own colour moving upward (`square ^ 56` for Black); bucket is `(file // 2) + 4 * (relative_rank >= 4)`. Include 12 piece identities × 64 squares, including kings. Feature index is `bucket * 768 + relative_piece_id * 64 + oriented_square`. Relative piece ID is 0–5 for own P/N/B/R/Q/K and 6–11 for enemy pieces.

Embedding shape **(6144, 32)**, float32 during training, int16 export. Shared bias **(32,)**. Keep separate White and Black perspective accumulators. Apply clipped ReLU to each and subtract the two perspective activations for a colour-antisymmetric residual. Output weights **(32, 2)** for middlegame/endgame interpolation using the existing 0–24 material phase. Keep the existing tempo handling in the base evaluator; do not accidentally count it twice. Output residual is in White's perspective, clipped initially to ±400 cp, then converted once to side-to-move in `evaluate_nb`.

This is a specified original architecture, not a translation of an opponent or another engine. The eight-bucket/32-unit choice is a bounded first candidate, not a tuned optimum. It aims to condition piece relations on king location while keeping state updates small. Its parameter/data ratio is a serious risk; the unconditioned old 16/32/64-unit trials already showed that a larger model on the old labels is not enough.

Training objective: Huber loss with delta 100 cp on leaf residuals, plus a pairwise ranking term only for stable reference separations ≥50 cp. Initially weight pairwise and scalar losses so neither contributes more than half the total batch loss; select the exact coefficient using training-only family folds. Root-pair loss must backpropagate through recorded alternative leaf representations with explicit parity, not confuse a root reference value with a raw one-ply static score. A simpler first pilot can omit the pair loss and evaluate ranking offline; record this ablation.

Predeclare a small regularization grid (for example 1e-4, 1e-3, 1e-2), two seeds, and early stopping on training-family validation. No outer-test model selection. Report MAE/RMSE, phase tails, confident pair misranking and learning curves at increasing data sizes. Use importance weights or capped per-root contribution to prevent eight correlated leaves counting as eight independent games. The original human validation set is a compatibility guard, not a blind gate.

### Quantization and runtime

Choose embedding/bias scale 128 initially, with int16 weights and **int32 accumulators**. Clipped activations are 0…128; output weights use a separately documented scale, initially 256, with int64 temporary reduction if the derived worst-case bound does not fit int32. Export exact integer rounding/division semantics shared by Python and Numba. These scales are proposals; select from a predeclared small grid using training validation and require negligible held-out ranking degradation.

Use declared weight bounds during training/export. For ≤32 pieces, require `abs(bias_int) + 32 * max_abs_embedding_int < 2^31`; derive a corresponding output bound including 32 units, activation limit, output coefficients and taper. Do not assume a low observed accumulator maximum is an overflow proof. Test colour inversion, promotions and legal material extremes.

The embedding is **393,216 bytes** at int16; two 32-unit int32 accumulators across 96 plies require **24,576 bytes**. Weight storage comfortably fits the submission budget. This arithmetic size is not a measured RSS or latency result.

In `core_nb.py`, add original `refresh_accumulators_nb`, `update_accumulators_nb`, and `residual_nb` kernels. Put/remove deltas account for captures, en passant, promotions and both rook/king castling moves. A king crossing buckets refreshes its perspective from the resulting board. Store/restores on the search stack, or prove exact reversible updates; don't combine two restoration strategies accidentally. Null moves change side-to-move only and leave piece accumulators unchanged. At root initialize from the FEN; TT entries remain position keyed and must be invalidated whenever weights/evaluation semantics change.

Warm the exact search/update/evaluate signatures at import; no PyTorch/ONNX runtime import. Load only original exported arrays with verified shapes/dtypes, within the current ready deadline. The measured 768×16 prototype gives 1.78× faster accumulator updates than refresh in an isolated ARM loop, **not** an integrated search speedup. King-conditioned 32-unit inference/update costs are still unmeasured.

## 4. Integration order and gates

1. **Rule-corrected fallback.** Predicate/native edge tests, differential perft only if move/state code changed, current-referee scripted games, then native Linux cold-import/deadline checks. Preserve a hash-bound v6 control.
2. **Offline instrumentation and data.** Prove fixed-node identity, source/reset/signature isolation, leaf-path reconstruction, family splits and duplicate exclusions. Freeze training/validation/test manifests before training. Do not tune against the 12 confirmation openings.
3. **Model pilot.** Linear control and one sparse residual architecture on identical data. Require at least 5 cp held-out MAE improvement **and** a meaningful reduction in confident pair misranking with no material phase-tail regression before integration. These are proposed practical screening thresholds, not calibrated Elo predictors. Reject or gather better data if both models remain within noise.
4. **Integer differential tests.** Full refresh versus updates and undo on ≥10k legal positions including explicit EP/castle/underpromotion/king-bucket boundaries; exact symmetry and bound tests; float/export inference agreement; unchanged mate/draw score domains. Existing 2,999-state prototype checks are useful scaffolding but insufficient for the new shape and integrated engine.
5. **Native cost gate.** One Linux CPU, no competing timed worker on that core, 2 GiB envelope, fresh exact-source cold imports. Measure eval/update mix and equal-node search throughput against released v6; target ≥0.90× v6 throughput. A larger loss needs independent equal-wall strength evidence rather than relaxing the gate from a pleasing MAE. Keep hard 400 ms clock margin and legal fallback.
6. **Mechanism and development games.** Use the old roots only as regression diagnostics. Run 12 development opening pairs at a fixed short wall clock, all variants reported, then a single 24-pair deeper screen if warranted. Include the rule-corrected fallback so a model's effect is separable from referee alignment. No repeated confidence-interval peeking.
7. **Fresh confirmation.** Use `lab/tempest/fresh-confirmation/openings.fen` once for the frozen finalist: 12 colour-reversed pairs. The manifest binds starting balance labels and exclusions. It is a cheap confirmation screen, not a precise strength estimate; consume it as used afterward.
8. **Final native promotion test.** Freeze a new independent set against the exact released v6 archive under current rules, optionally 48 pairs / 96 full 120+0.5 games as a fixed practical budget. With paired scores bounded in [0,1], the worst-case standard error at 48 independent pairs is about 7.2 percentage points; actual paired variance may be smaller. Such a sample can remain inconclusive for a modest improvement. Report its actual paired interval and operational results, don't promise a significance threshold will be reached. A calibrated SPRT is an alternative only if specified before running, not another test after peeking.

Wider guards: older current-rule-compatible Storm/v5 controls, a legal original tactical search setting, and diverse e4/d4/flank/locked-centre/open-king/passer/rook-ending starts. Public ms/AI Fellows/AlphaFish PGNs supply diagnostic positions, **not opponent engines**; do not claim a head-to-head result against them. Reference Stockfish remains offline only.

Rollback conditions: any illegal/crash/flag/init failure or deferred signature; inconsistent accumulator/undo; label or family leakage; unverified source identity; significant phase-tail/ranking regression; cost that erases equal-wall gains; later-game damage from a clock change. A failed model gate returns to the rule-corrected v6 fallback. Do not promote the current R&D pruning ablations or the 12-relation fit.

## 5. What the implementation agent can use immediately

- `lab/tempest/README.md`: exact reproduction sequence and portability limitations.
- `experiment-plan.json`, `corpus-v1.json`, `split-manifest.json`: frozen discovery inputs and initial reservations.
- `prototypes/`, `probe.py`, all `*-probes.jsonl`: isolated v6-based ablations, traces, hashes and A–B–A controls.
- `reference-corpus.jsonl`, `reference-choices.jsonl`, `public-deep.jsonl`, `opponent-critical-summary.json`: finite same-root evidence with node budgets and histories.
- `eval_experiment.py`, `eval-relations/`, `label-audit.jsonl`: original relation control and label-quality evidence.
- `accumulator.py`, `accumulator-result.json`: original reversible integer prototype using our own prior weights; not deployment-ready evaluation.
- `rule-probe.json`, `referee-diff.patch`, `history-audit.json`: current-rule change and exact limits of old draw evidence.
- `fresh-confirmation/`: twelve unused balanced opening families; no candidate results exist.

No source in `tempest/` or Linux submission archive was created by R&D. The next agent's first concrete deliverable is a tested rule-corrected fallback plus the hash-bound leaf-data interface, followed by the gated evaluator pilot. This specification supplies a falsifiable architecture and stop conditions; it does not rename an unproven prototype as a stronger release.
