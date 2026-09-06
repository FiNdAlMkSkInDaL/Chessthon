# Storm r3 evaluation experiment

This is an isolated challenger to Storm r2, not the v4 release candidate. Its source is in `dist/storm-eval-r3`; the release source in `storm` was not edited. The Windows archive is for local comparison only: `dist/storm-eval-r3-experimental-windows.zip`, SHA-256 `6c5773cdd7493b9d64330d3046cf2ba50f42061099619d725d7a2ae65d7784ef`.

## What changed

The existing exact incremental PeSTO material/PST score remains intact. A separate, tapered positional correction adds the following original, untuned terms. No recorded FEN, move, opening or opponent is hardcoded.

| Term | Middlegame / endgame scale |
|---|---|
| Safe mobility | N 4/3, B 4/4, R 2/3, Q 1/2 cp per accessible square above neutral counts 4, 7, 7, 14. Excludes friendly occupancy and enemy pawn attacks. |
| King pressure | Requires at least two attacking pieces in the king ring. Quadratic coordination penalty, capped at 250 MG cp; halved without the attacker's queen. |
| Pawn shelter | Up to 48 MG cp, scaled by opposing attacking material. |
| Passed pawns | Only genuinely passed front pawns; MG advancement 2, 6, 12, 24, 48 and EG advancement 6, 16, 36, 75, 140 cp from relative ranks 3–7. |
| Passer support | Advanced-pawn king-distance adjustment bounded at 40 EG cp; immediate blockers halve the bonus. Conservative pawn-only square-rule bonus 80 EG cp, without a side-to-move assumption. |
| Bishop pair | Opposite-color bishops only, 24/36 cp. |
| Bare-king conversion | Encourages restricting the defending king to the edge and approaching with the winning king, only with suitable mating material. |

Raw corrections are white-minus-black and independent of turn. Tapering rounds symmetrically, separately from the inherited PeSTO floor division. The referee's late material-adjudication evaluator bypasses all these corrections.

## Correctness and cost

`lab/storm/test_eval_design.py` independently checks 212 pawn-attack maps, 270 positions under color/horizontal/turn transformations, passed-pawn geometry and king/blocker cases, phase saturation, adjudication bypass, and 130 make/unmake edges against fresh FEN evaluations. All pass. The largest absolute correction in that corpus was 290 cp. Two implementation defects, signed shelter rounding and a truncated bishop-color mask, were caught and fixed before measurements.

The same 32 PGN positions at completed depth five gave:

| Local Python 3.12 screen | Storm r2 | Evaluation r3 |
|---|---:|---:|
| Nodes | 425,503 | 438,072 |
| Search time | 1.524 s | 2.516 s |

This is **65% more search time**, with only 3% more nodes. Full piece mobility on every evaluation is a material cost, and the experiment needs a playing-strength gain to justify it. A cached-position microbenchmark measured about 2.03 microseconds per r3 evaluation; whole-search results are the more relevant measurement. These are Windows ARM/emulated-x64 observations, not tournament hardware claims.

The exact archive was freshly extracted and imported through the normal lab runner on CPU 8 with a 2 GiB Job Object. Import took 46.376 seconds, total process time 49.870 seconds. Both Numba dispatchers were compiled, original readiness was true, and no fallback/readiness override was used.

## Difficult-game diagnostics

Identical 3-second hard/soft allowances were supplied to each engine with empty TT, killers and heuristic history, while preserving actual PGN repetition history. The two R12 preferences are historical site-review labels already recorded in `V3_VALIDATION_2026-09-04.md`; other move differences are unlabelled diagnostics.

- R12 move 16: r2 and r3 both retain `Nxd6`; neither selects review-preferred `Nxc5`, including at the 9-second follow-up.
- R12 move 24: r2 and r3 both retain `Rh3`; neither selects review-preferred `Rb3`, including at the 9-second follow-up. V3 selects unlabelled `Kc2`.
- R4 move 13: all retain `...Qd8`; extra reported depth has not changed the choice.
- R13 move 31: r3 selects `...c4` at the 3-second allowance; r2 and v3 select `...Bb6`. The previous review had called attention to missed `...c4` pushes around moves 31–32. This is a promising diagnostic observation, not independently verified optimal play.

The 9-second follow-ups are diagnostic probes of stubborn positions, not a proposed per-move clock policy. Supplied budgets are identical, but controllers stop at different times; reports include actual elapsed time and completed-iteration traces. Selective depth numbers are not equivalent search coverage between versions.

## Experimental match gate

Four paired openings, indices 144–147, were scheduled with 10 seconds plus 100 ms per move, colors and CPUs 8/9 swapped within each pair. The baseline was the signed `dist/storm-r2-linux-x86.zip`. Each game used fresh processes and exact archive snapshots, the unchanged referee, pinned single CPUs and a 2 GiB memory cap.

**The screen stopped at its failure gate in game five.** The raw score was **+3 =0 -2**, comprising four played games (+3/-1, all checkmates) and an initialization loss. Only two pairs completed: r3 won both colors on opening 144, and opening 145 split by color. The incomplete screen is not promotion evidence or an Elo estimate.

The failed r3 process eventually reported a successful 87.842-second Numba warmup and original readiness true, but actual import took **92.817 seconds**, beyond the 90-second allowance. No readiness override or Python fallback was used. This failure remains in the raw record despite the earlier 46.376-second preflight pass. It establishes that this Windows cold-import screen failed, not that the candidate has a measured Linux failure; a native test would be separate evidence.

No baseline failure, resource-envelope configuration problem, or archive mutation was reported. The match process exited and its CPU 8/9 children were gone before those CPUs were released for the r2 supplementary stress test. The r3 source remains frozen and experimental; r2 release work is unaffected.

Raw results: `lab/storm/eval_r3_vs_r2_screen.jsonl`; console output: `lab/storm/eval_r3_vs_r2_stdout.log`. No source edits are permitted after packaging. The disjoint native r2-vs-v3 holdout remains the release work.

Reproduction scripts and reports: `lab/storm/test_eval.py`, `lab/storm/diagnostic_compare.py`, `lab/storm/preflight_eval_experiment.py`, `lab/storm/eval_design_r3.json`, `lab/storm/eval_r2_benchmark.json`, `lab/storm/eval_r3_benchmark.json`, `lab/storm/diagnostic_comparison_eval_r3.json`, and `lab/storm/eval_r3_cold_preflight.json`.
