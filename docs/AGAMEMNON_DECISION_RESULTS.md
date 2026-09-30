# Agamemnon: training the backed-up decision

6 September 2026. Research in `lab/agamemnon_decision/`. **This report is in progress while independent confirmation finishes.** Tempest r1 remains the competition release.

## What was built

The approved branches are implemented: actual own-search PV endpoint collection with legal histories; stronger offline alternative labels and refutations; broader game/opening coverage; matched preference/static/mixed/replay objectives; 25%/50% hybrid controls; and a small original nonlinear mover/opponent head. This is 32 distinct training fits plus six deterministic snapshot reruns, and 17 completed Linux source variants with 3,740 decision searches. Playing results, not training loss, determine the next gate.

## Dataset and provenance

The source is a bounded 64 MiB prefix of the [January 2025 Lichess rated standard game export](https://database.lichess.org/standard/lichess_db_standard_rated_2025-01.pgn.zst), under the standard-game [CC0 licence](https://database.lichess.org/). HTTP range and source hash are recorded in `data/`. Prefix hash: `e55f74cf00e1e081c583e5d05d8b92715c04d3c0ad7479bc1778009e39795624`. This is a filtered chronological prefix, not a representative random sample of all chess. TWIC was investigated but not downloaded or used.

After scanning 23,469 games, preparation selected 3,200 roots with distinct game IDs and canonical positions at ply20, unique exact/mirrored root positions, ratings at least1800 and base time at least180seconds. One even-ply24–80 root per game, nonterminal and initially balanced by the recorded filter. Original legal UCI histories are retained. The split was frozen before labelling: 2,560 training,320 development,320 sealed. Only the2,880 nonsealed roots were collected and opened. Distinct ply20 families do not establish broad ECO independence or disjointness from the anonymous prior4.1-million-position pretraining corpus.

The source is the original turn-aware checkpoint `lab/agamemnon_scale/turn-aware/s260909/adapted.npz`, SHA256 `2077cb3690feedb8d9fa2424aa13636bc1ee5597aa3bb3ed3c00326f90ad0de9`. Collection uses its50% hybrid. The selective search propagates the exact endpoint and PV of each backed-up best child through metadata rows of its existing accumulator storage. TT/pruning/draw paths without traceable evaluation provenance are excluded. Sixteen trace-on/off identity checks preserved move, score and nodes. Each PV is legally replayed, and endpoint position, turn, counters and score perspective are verified.

Each alternative has a fresh TT and full root window, requested depth5 with100k-node cap and fallback to a completed depth4/3. This is the actual search policy at fixed depth, not competition iterative timing. The offline teacher is Stockfish19, one thread32MB hash, never shipped:64k-node MultiPV3 shortlist, then an independent forced32k-node search for each retained alternative. The shortlist combines the student choice, teacher choices, played move and deterministic random move. Full game history is supplied. Labels use the latest complete unbounded streaming result, avoiding stale bound flags in aggregated analysis dictionaries. Finite teacher scores are estimates, not exact minimax values. Teacher PVs/refutations are preserved as research data; they are not runtime answer tables or an additional learned policy head in this cycle.

Collection completed2,880 roots,12,293 labelled alternatives and11,927 traceable own-search endpoints. The first dataset required no legal captures/promotions at the endpoint, leaving only1,313 leaves across441 training and56 development groups. That was too restrictive: a valid qsearch stand-pat endpoint can have captures available after the selective search resolves them.

We therefore reran all11,927 traced alternatives with an additional stand-pat-beta-cutoff marker. Every retrace preserved the original move, score, depth, node count, PV, endpoint and White score; all11,927 endpoints were non-beta-cutoff endpoints. `dataset-settled/` retains11,582 eligible leaves across2,428 training and307 development groups after nonmate/score filters, exact/mirror cross-split removal and requiring multiple alternatives per group. Selective pruning remains part of the teacher-to-student target mismatch; these are not exhaustive proofs of quiescence.

The pilot had an ancillary feature bug: an extra side sign was applied to an already-White handcrafted evaluation when constructing the hybrid base. Search scores/PVs were unaffected. Raw pilot records and earlier source versions remain preserved. Dataset preparation explicitly repairs the pilot schema; expansion writes `white-v2`. Prepared floating reference values agree with recorded quantized native values within1.475cp on the settled dataset.

The full independent replay audit passed all12,293 teacher PVs and11,927 own PVs, including legal histories, endpoint state, perspective and split checks. Teacher and student differed on the first opponent reply in6,516 recorded lines; this is a disagreement diagnostic, not evidence of a model improvement. See `audit.json` and `audit.py`.

## Controlled objectives and capacity

`fit_decisions.py` implements a semi-gradient objective through frozen student PV endpoints. Within a round all objective arms share initialization, training data, seeds, batches, replay draws, rates and update schedules. Pair preference, static target loss, half-pair/half-static and replay-only are contrasted. Development conditional regret chooses among retained alternatives; it is not full legal-move regret or playing strength. The original replay-development MAE guard is235cp.

The hard round used gaps>=40cp,16epochs, learning rate0.00015 and replay gradient weight1. All four objectives across two seeds, plus primary-seed nonlinear pair/static arms, selected epoch0. Of139 initial training mistakes,87 had regret below40cp and were excluded by the threshold.

The soft round used gaps>=5cp, teacher preference probabilities with120cp temperature,128epochs, rate0.0005 and replay weight0.25. These are multiple simultaneous changes from the hard round; between-round effects cannot be attributed to softness alone. The four objectives and both nonlinear arms ran in both seeds. New objectives still selected epoch0 on the strict dataset; replay alone yielded small improvements. Six primary-seed runs were reproduced with fixed snapshots16/64/128. Their selected arrays match the originals bit-for-bit. Before fresh-search results were observed, the fixed epoch64 snapshots were nominated for Linux diagnostics, bypassing only the frozen-PV selector, not the strength/release gates. This amendment is preserved in `FRESH_SEARCH_AMENDMENT.md`.

The original nonlinear residual head combines mover/opponent32-unit activations into64 inputs and16 hidden units, then two phase outputs. Zero residual-output initialization preserves the existing function exactly. It retains the original integer incremental embeddings and adds float weights, with no Torch/ONNX dependency. It passed63 gradient checks, colour/turn symmetry, and native/reference checks. Capacity alone did not produce the best diagnostic candidate.

The broader settled dataset trained four objectives in two seeds under the soft schedule. Preference training improved the starting conditional regret29.3485cp to27.1075cp (seed260916,epoch1) and27.0651cp (seed260917,epoch4). Mixed/static selected epoch0 in both seeds. Replay selected29.3029cp in one seed and epoch0 in the other. This is replicated evidence on the conditional surrogate, not yet an independently confirmed chess-strength effect. The primary preference checkpoint SHA256 is `5d49ca1eabddecde6e796e6ec2aadaae103993b5f2ffe780bcfd382e3ec692d3`.

Execution count:2 pilot fits,10 hard-round fits,12 soft-round fits,8 broader settled fits =32 unique fits;6 soft snapshot reproductions =38 optimization executions. Four settled primary runs saved snapshots on their initial execution and are not counted twice.

## Linux fresh-search diagnostics

All17 variants completed six perft cases, ABA reset checks and cold import below the80s research guard. Each of16 neural variants passed5,288 exact integer accumulator positions and native output-reference checks. There were3,740 searches:110 existing exposed development roots × two allowances ×17 sources. Per-root allowances were200k nodes and300ms; the unchanged iterative clock can return earlier. At most two active searches ran on separate pinned VPS CPUs, with1800MB/no-swap service limits. These are research processes, not a complete no-network competition certification.

Regret below is capped at500cp. Teacher answers for this old diagnostic set are finite16k-node full-alternative labels. Root-paired bootstrap intervals are exploratory and unadjusted for repeated development use and multiple comparisons; see `results.json`.

| Variant | Fixed-node regret cp | Wall regret cp | Wall errors >200cp | Game nominee |
|---|---:|---:|---:|---|
| Tempest |25.86|23.01|1|Control|
| Original mix25 |18.38|20.85|1|Control|
| Original mix50 |20.05|17.61|1|Control|
| Mixed25 |20.55|17.04|0|Yes|
| Mixed50 |22.25|24.87|1|No|
| Pair-deep25 |24.53|21.10|1|No|
| Pair-deep50 |22.65|23.66|1|No|
| Pair25 |22.35|22.25|1|No|
| Pair50 |22.96|23.47|2|No|
| Replay25 |20.85|16.19|0|Yes|
| Replay50 |23.29|20.85|1|No|
| Static-deep25 |18.56|17.31|1|Yes|
| Static-deep50 |24.90|24.82|2|No|
| Static25 |20.26|16.86|1|Yes|
| Static50 |23.26|23.43|0|No|
| Settled-pair25 |18.46|15.16|0|Yes|
| Settled-pair50 |26.80|24.55|3|No|

Frozen nomination required at least5cp better equal-wall capped regret than repeated Tempest, no additional>200cp errors and no fixed-node regression. Five candidates passed. Mixed25 went first, then replay25 as the strongest first-cohort/control result, then settled-pair25 after its later probes. Static25 and static-deep25 were diagnostic nominees but have no game results in this cycle. A good replay-only control prevents attributing all improvement to novel supervision. The25%/50% differences also show that integration weight can reverse the result; do not transplant the trained evaluator at full weight.

## Paired development games

Frozen plans use eight exposed development opening families, both colours,16games per candidate,500ms maximum wall allowance per move, original clock drivers and complete source hashes. Every declared game finishes irrespective of intermediate results. Threshold: below50% rejects,50–60% is inconclusive, at least60% permits independent confirmation only after runtime/protocol gates. This is not the120s+0.5s competition clock; operational success here cannot certify a competition flag rate. Source workers retain a stale text label saying twelve smoke games; frozen plans, indices and completed summaries specify16.

| Candidate | W/D/L | Score | Opening-paired exploratory95% interval | Decision |
|---|---|---:|---|---|
| Mixed25 |6/6/4|56.25%|37.5–78.125%|Inconclusive|
| Replay25 |7/6/3|62.5%|40.625–78.125%|Eligible for independent confirmation|
| Settled-pair25 |4/10/2|56.25%|50–65.625%|Inconclusive|

All48 games completed, with6,735 legally replayed plies, correct terminal outcomes and source bindings. There were no worker crashes or illegal moves. Fixed per-move clocks do not certify a competition flag rate. Replay25, the ordinary continued-training control, is the only candidate that crossed the predeclared60% game threshold. Its wide confidence interval does not establish superiority.

## User-requested blend tuning — completed

The user then asked to test around25%. `blend-plan.json` freezes15/20/25/30/35% for the primary settled-pair checkpoint. Weights and search policy remain fixed; only the interpolation expression changes. The unchanged25% source is repeated on both CPUs at opposite ends of the sequence. Six probe executions include four new blend variants and two identical-source control repeats. Do not count the latter as two new architectures.

The selector requires lower wall regret than the mean repeated25% controls, no additional large-error count versus the worse control, and no fixed-node regression. The best eligible challenger plays16 direct development games against25%. This is a local exploratory sweep, not a global optimum claim. No narrower follow-up grid is selected from the same results. The fresh confirmation outcomes are not used for this tuning.

| Neural weight | Fixed-node capped regret cp | Wall capped regret cp | Wall errors>200cp |
|---|---:|---:|---:|
|15%|20.85|21.55|1|
|20%|20.92|19.35|0|
|25%, CPU0 repeat|18.46|15.17|0|
|25%, CPU1 repeat|18.46|15.35|0|
|30%|22.67|20.05|1|
|35%|23.70|21.31|1|

The two25% controls were identical in move, score, nodes and regret at fixed nodes on all110 roots; their wall moves differed on3roots. Mean wall regret15.2636cp remained lower than every neighbour. No challenger passed the frozen gate, so no direct blend match was warranted. This establishes25% as the best tested local value for this checkpoint, not an exact/global optimum. Combined probe count is23 executions (21 distinct source variants plus two repeat controls),5,060 development searches. All completed the native research checks.

## Training-only label-stability diagnostic

While confirmation ran, `label_stability.py` compared existing64k-node MultiPV estimates with independent forced32k-node labels, using only the2,560 training roots. On2,513 common nonmate shortlists, the best choice changed600times;7,520 shared alternative scores had median absolute change16cp,90th percentile61cp. Pair rankings reversed in16.10% of comparisons with initial gap>=5cp,11.33% with gap>=20cp,6.80% with gap>=40cp and2.70% with gap>=80cp. Search budget/allocation/depth differ, so neither estimate is a truth label. This measures sensitivity, not teacher error.

The settled primary preference fit's epoch128 conditional regret52.32cp and old-distribution MAE297.55cp were worse than its epoch1 selected regret27.11cp and old MAE215.68cp. The selected replication was epoch4. More epochs on these fixed noisy targets is unsupported. A future branch should allocate extra teacher budget to uncertain/refutation-changing comparisons and refresh student PV endpoints after a small update, contrasting it with matched replay. No weights, labels, checkpoint selection or confirmation plan changed from this diagnostic.

## Independent confirmation — running

Replay25 is frozen as the sole current confirmation nominee in `CONFIRMATION_PLAN.md`. It has been packed on Linux as `a72338865851743b0f50ce2796c20eb3c3cc88f66c2e91c83e970e83fa36b58c`; every source/data member matches its development worker manifest. The exact-archive native/protocol/resource gate passed: structural cold35.319s, official-runner protocol cold34.352s, six perft cases, deadline/cap/history probes, legal protocol responses and enforced CPU/RAM/no-IP-socket-creation checks. Known signer limitations remain documented in the gate.

The bounded plan now uses all12 reserved opening families, both colours,24 full120s+0.5s games and fresh processes. Target: score>=55%, paired95% lower bound>50%, zero faults. Plan SHA256 `fd0279a83a3ed6ebfa887dabbb2c3d282d7f811f0f80ca6149e59e9d48137a16`. These families are now consumed for independent confirmation. This is separate from a112-game release guard, and never automatically promotes an archive.

## Release and continuation

No release is nominated yet. The320 sealed roots remain unopened. The12 reserved confirmation families are now assigned to the frozen replay25 test and must not be called unused in future work. the signer archive (not in git) remains Tempest r1, SHA256 `0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4`. Canonical `tempest_exact/` and the official harness are unchanged. Transport zips are research artifacts, not upload archives.

The live [AI Chessathon documentation](https://aichessathon.com/docs) was checked this turn: original models and offline engine-labelled training are permitted; published networks, third-party engine ports and runtime engine-answer databases remain excluded. All new model implementations and weights here are original; Stockfish is confined to offline research.

Reproduce summaries with `summarize.py`, data checks with `audit.py`, and completed-game checks with `audit_matches.py`. Plans, manifests, checkpoints, source versions, native source hashes, curves and per-root results are preserved under `lab/agamemnon_decision/`; matches are under `lab/agamemnon_scale/match-backed-*`.
