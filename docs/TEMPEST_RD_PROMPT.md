# Tempest: research brief for a fresh instance

You are the R&D agent for **Tempest**, the next generation of our AI Chessathon engine. Work in this Chess TK workspace. The user will bring your final report back to the implementation agent, which will build, test and package the next submission. Your job is to discover and substantiate the best next architecture and improvement programme, using actual research and bounded experiments—not merely write a plan for someone else to research.

We want a substantial improvement against strong competition. Question inherited assumptions when evidence warrants it. Do not mistake a list of familiar chess-engine features for an explanation of what limits this engine. Equally, do not pursue novelty for its own sake or promise a leaderboard position. A rigorous negative result is useful if it narrows the next build decision.

## 1. Start from the correct baseline

Read `AGENTS.md`, the current amendments and relevant sections of `ENGINEERING.md`, then:

1. `docs/ODIN_V6_RELEASE_REPORT.md`
2. `docs/ODIN_DAY3_REVIEW.md`
3. `docs/ODIN_V6_MORNING_REVIEW.md`
4. `docs/FAST_ITERATION_PROTOCOL.md`

Inspect the actual implementation in **`odin_v6/`**, particularly `agent.py`, `core_nb.py`, `storm_clock.py` and `history.py`. Read older reviews selectively where they explain a specific experiment. Historical status paragraphs and old prohibitions can be superseded by later amendments; do not reset the project to its earliest doctrine.

At handoff on 6 September 2026, Desktop `agent.zip` is released **Odin v6**, SHA-256:

`cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647`

Its canonical Linux archive and evidence are under `lab/odin/native_release/odin-v6-architecture-r1/`. Desktop `Odin-v6.zip` is identical. Verify current hashes before relying on this identity. **`odin_submission/` is v5**, while `odin/` is an older experimental branch and `dist/agent.zip` is historical v1. Several experiment scripts still default to v5: explicitly bind source paths and hashes to v6 and record any harness adaptation.

Preserve all release sources, Desktop archives, frozen plans and raw evidence. Work in `lab/tempest/` and isolated prototype sources. Do not upload, promote, overwrite `agent.zip`, restart old finalizers or remove their stop markers. This task authorizes research, original prototypes and bounded tests on existing resources. It does not authorize buying compute or contacting other people.

## 2. What we actually know

V6 beat exact released v5 in **112 full-clock games: 30 wins, 69 draws, 13 losses**, scoring **57.59%**, with a paired 95% interval of **52.23%–62.95%**. The match-relative estimate is approximately +53 Elo, not a prediction of ladder rank. Both engines had zero operational failures. All 14,743 legal plies were replayed and audited. The 56 paired openings have now been inspected and are **used data**, not a fresh Tempest holdout.

The automatic final audit initially failed to import `harness` after the games finished. The unchanged validator subsequently passed on Linux and independently locally with the pinned harness import path. Use `overnight112/review-audit.json` and `local-review-audit.json`, alongside the raw lanes. Do not interpret the preserved original error as failed games or imply that the automatic report originally succeeded.

V6 primarily made v5's decisions cheaper: direct legality/check tests, pin shortcuts, capture-only quiescence generation, first-blocker ray operations and arithmetic-equivalent fused evaluation. A controlled 40-position native benchmark measured **1.5714× throughput with identical equal-node moves, scores, depths and node counts**. Search settings and fitted evaluation weights remained unchanged. That is a real advance, but it leaves many decision-making assumptions unchanged.

V6 already has bitboard Numba search, TT, PVS, LMR, null move, reverse futility, quiet futility, internal iterative reductions, SEE pruning, check extensions, PeSTO plus 24 original fitted features, adaptive time allocation and current-referee history handling. Verify these in code rather than proposing them as absent. Its clock already responds to root stability, score drops and iteration cost.

The draw count alone does not establish saturation. More diagnostic evidence: v5 and v6 chose the same moves at all eight selected Day 3 roots under reconstructed recorded-clock probes, despite v6 reaching an extra depth at five. Those probes reconstruct history but clear the TT; they do not reproduce the complete live internal state. Fixed three-second probes changed one move, without establishing it was better. Determine the causes, rather than declaring this proof that evaluation or pruning is at fault.

The four Day 3 games available at the last review were rounds 31–34: a win against xx and losses to ms, AI Fellows and adashima. They correspond to the user's reported **v5 upload before v6 promotion**, not site evidence for v6. Inventory the folders again for newer games and record version confidence; PGNs do not necessarily identify archive hashes.

Useful diagnostic roots include 12.Rae1 and 17.Qg4 against ms, 10...Be6 and 24...Bxe4 against AI Fellows, and 20.exf5 and 21.e7 against adashima. Several occurred with 70–107 seconds remaining. Same-root two-million-node Stockfish comparisons support concern about these decisions, but their scores are finite-search estimates. Some earlier shallow accusations did not survive deeper analysis. Read the review before repeating a diagnosis.

## 3. Study the opponents, with evidence

Investigate what stronger opponents achieve that we do not, using **ms and AI Fellows as anchors**, plus roughly three to five strong or stylistically different teams and appropriate peers. Include leaders such as AlphaFish where usable public games exist. Examine losses and draws as well as attractive wins, both colors, opening families and opponent strength. Do not train a bot solely to beat two named teams.

The [leaderboard](https://aichessathon.com/leaderboard) snapshot checked on 6 September showed AI Fellows at #12 with 17–3–4 and ms at #14 with 19–3–6. These are dated observations. Ratings and cumulative records mix submissions and opponents; they cannot identify an algorithm or isolate a version's strength.

Public starting points:

- [AI Fellows](https://aichessathon.com/team/b574c0ea-e994-4a16-9918-7fbc989c4234?from=lb)
- [ms](https://aichessathon.com/team/c3e1bc09-3d21-4279-ace0-16bb3742f5da?from=lb)
- [AlphaFish](https://aichessathon.com/team/659a3020-8af7-4934-b753-3b7c5fd11184?from=lb)

**Check freshness:** during handoff research some team URLs returned older snapshots than the leaderboard, and another navigation URL returned newer rounds. Some historical results were subsequently marked void. Timestamp retrievals, reconcile game IDs and rated/void status, and separate current records from cached pages. Never count a void or unterminated game as a rated result. It may supply explicitly labelled partial behavioral evidence.

Acquire a manageable, diverse public PGN sample through observed public links or ordinary browser use. Save provenance and a reproducible manifest. Use only public or our own authorized data. If public move timing is absent, say so; our own engine logs do not reveal the opponent's depth, NPS or search budget. Read legitimately available technical descriptions if any, but do not assume private source access.

Produce a comparative profile: opening handling, tactical accuracy, defensive resources, treatment of pawn breaks and king safety, passed-pawn races, simplification choices, conversion, repetition and time use. Normalize for position difficulty, material, forced moves, color and opponent quality as far as the data permits. Reconstruct critical opponent-turn positions and our available defenses; test whether v6 finds their strong moves with comparable budgets. Analyze first consequential divergence and later recoverable opportunities rather than merely the last blunder.

For every claimed difference label it **observed**, **inferred**, or **not identifiable from available evidence**. “They accelerate late” does not demonstrate a sophisticated importance model: forced moves, smaller trees, a stable PV, clock pressure or a winning position are alternatives. “They find positional moves we miss” does not establish neural evaluation. Frame competing explanations and run a discriminating test. Never infer misconduct from strong play.

## 4. Find the mechanisms that limit us

Build a compact, versioned diagnostic corpus from our games, opponent games and independent positions. Preserve complete available history and remaining clocks where relevant. Keep discovery positions separate from untouched confirmation positions, grouping by game/opening family and deduplicating transpositions. The existing Day 3 roots are discovery data. Broad coverage must include positions where v6 plays well, not just selected failures.

Use interventions to distinguish causes. Examples to consider, not a compulsory shopping list:

- **Evaluation and representation:** compare candidate ranking before search, after controlled search and against deeper multi-PV reference analysis. Test whether the current feature set misses pawn-break consequences, king exposure, piece coordination, restricted pieces, connected passers or transitions. Separate horizon effects from static scoring errors. Investigate richer original evaluation, efficient learned pattern representations or a CPU-feasible incremental network if evidence supports them. Compare a strong simple model with any neural prototype on identical splits and labels.
- **Search selectivity and ordering:** disable or vary one pruning family on diagnostic roots at controlled cost. Identify whether the good move is reduced, pruned, ordered too late, or evaluated incorrectly at a leaf. Record branching, re-searches, cutoffs, TT behavior and completed iterations where instrumentation can do so faithfully. Search-depth numbers alone do not show equivalent coverage. Extensions, verification searches, alternative root selection or uncertainty-aware search are hypotheses requiring benefit-versus-cost evidence.
- **Time as a decision resource:** measure how move quality responds to additional budget across position types, not merely total unused seconds. Test recorded-clock, fixed-node and equal-wall budgets for distinct questions. Include realistic replay with persistent state where practical. Design a clock change only if it directs time toward decisions with measurable marginal benefit without creating later losses. V6 already finishes the native match with a median 6.856 seconds, so the original observation of 25 seconds unused is not a current universal premise.
- **Training and data quality:** examine label noise, tactical contamination, phase coverage, near-duplicates and correlated opening families. Consider deeper labels at informative positions, disagreement-driven sampling, original self-play and phase-aware calibration. Explain what new examples teach that existing data cannot. Keep offline strength gains distinct from inference cost, quantization loss and actual playing strength.
- **Endgames and draw behavior:** audit whether repetitions escape losses, discard wins, or follow objectively equal play. Inspect pawn endings, conversion and referee claim boundaries. Any draw-aversion or risk-sensitive policy must improve expected score across stronger and weaker opposition; avoid sacrificing sound draws just to reduce the draw count. Reverify any proposed book/tablebase legality and practical value under curated openings and the sandbox.
- **Higher-level architecture:** ask whether the highest-return change is representation, search organization, state reuse, data acquisition or a combination. A broader rethink is welcome, but require a plausible one-core cost model and at least a small falsifiable prototype before recommending replacement of the engine.

Use primary papers and official technical documentation for external research. Read published concepts, then derive original implementations. Do not port or translate another chess engine. Explain why a proposal fits this engine and this contest better than its alternatives.

For each serious hypothesis specify: evidence; competing explanations; smallest decisive experiment; expected benefit and downside; CPU/RAM/import implications; what would falsify it; and the gate required before it could ship. Investigate a broad set initially, then concentrate compute on the few with evidence. Do not manufacture ten variants of the same weak idea to satisfy a population count.

## 5. Reuse the research assets without repeating their mistakes

Available data and tools include:

- `Chess_results_day1/`: 15 v1 games and logs; `chess_results_day2/`: Storm rounds 16–30; `Chess_results_day3/`: Odin games. Re-enumerate current contents.
- `lab/storm/Storm-v4-vs-v3-games.pgn` and other Storm match evidence.
- `lab/odin/day3/`: 485 screened positions, deeper same-root references, `selected-roots.json`, `v5-probes.jsonl`, `v6-probes.jsonl` and `review-summary.json`. Scripts include `prepare_review.py`, `deep_review.py`, `summarize.py`; `lab/odin/new_games/probe_odin.py` reconstructs served-position history for probes.
- `lab/odin/training/`: public human PGNs, a provenance-bearing 20k-position corpus and older shallow reference labels. `lab/odin/quiet_eval/fit-records.jsonl` contains 5,601 deduplicated quiet resolved examples labelled at 100k Stockfish nodes, with 4,247 train and 1,354 validation examples. Inspect partitions and provenance before reuse.
- `lab/odin/quiet_eval/expanded_fit.py`, `expanded-matrix.npz` and `expanded-result.json`: original 24-feature fit. Held-out MAE improved modestly, approximately 99.47 to 97.24 cp.
- `lab/odin/fast/network-training/`: 12 small original network experiments, 16/32/64 hidden units, clipped ReLU and quantization. Best reused-validation MAE was approximately 96.81 versus 97.25, with longer training overfitting. They were not integrated. This rejects that small-data experiment, **not neural evaluation in general**. Reused validation is no longer blind.
- `lab/odin/fast/worker.py`, `match.py`, `population.py`, `generation_report.py`: warmed fixed-node screens and replay audits. Workers reset module state, test A–B–A determinism, reject silent native fallback and bind source/helper hashes. Understand the reset and instrumentation contracts before changing them.
- `clock_worker.py`, `clock_match.py`, `audit_clock_screen.py`: short equal-wall development comparisons. These are not full 120-second games. `bench_fused_search.py` supports controlled equal-node throughput tests; bind the baseline explicitly to v6.
- `generation_openings.py`, `openings.py`, `audit_openings.py`, and `lab/odin/release_openings/`: opening provenance and family exclusions. All previously inspected screening and final-match families must be treated as used.
- `lab/odin/release/native_gate.py`, `linux_match.py`, `validate_match.py`: native cold import, correctness, timing, pinned-referee full-clock matches and audits. The official harness is in `lab/odin/official-harness-91f70e54/harness/`, pinned to commit `91f70e54be07e1bf56311962044a08b822c3af50`. Do not modify it.

The previous parameter generation had 14 candidates screened in 252 short games. Apparently large early gains disappeared in deeper screens: IIR-off 52.08%, SEE ordering 50%, later IIR 48.96%, combined 48.96% over 48 games each. A continuation-history candidate also failed to establish improvement. Do not rediscover these as proven gains or treat their rejection as proof every related method is exhausted.

Use successive screening: correctness and mechanism probes → cheap paired development tests → fresh-family confirmation of promising finalists. Equal-node tests isolate decision changes; equal-wall tests capture speed/cost. Use both when necessary, without conflating them. Predeclare evaluation criteria, keep raw evidence and report every screened variant to control selection bias. Do not repeatedly inspect fixed-sample confidence intervals as if they were a valid sequential stopping rule.

Do not run another 112-game match per idea. The implementation agent will run the decisive promotion test after a candidate exists. Recommend a fresh, frozen final test against **released v6**, plus useful older/opponent-style guards, and explain the sample size and uncertainty. The inspected v5–v6 match is valuable diagnostic data, not an untouched final benchmark.

## 6. Tools and compute actually available

You can read and write files, run PowerShell and Python, implement original NumPy/Numba prototypes, profile code, fit original models, analyze PGNs, browse public sources and run independent experiment processes. Inspect your session's exposed tools and instructions; capabilities vary between fresh instances. Use browser automation if available and needed. Do not assume private accounts, undisclosed APIs, a GPU, extra paid compute or an opponent engine download exists. Assistant subagent delegation is available only if your session instructions permit it; process-level parallel experiments do not require extra assistant tasks.

**Laptop:** Windows ARM64, 10 logical CPUs and 16 GB RAM at last inventory. Use `C:\Users\finla\AppData\Local\ChessTK\venv312\Scripts\python.exe`; the incidental default Python 3.14 is not the runtime of record. Check actual resource use before choosing concurrency. Pin CPU-heavy workers, avoid oversubscribing timing experiments, and leave memory/headroom for the user. Start background Windows helpers with `-WindowStyle Hidden`.

**Offline reference:** `C:\Users\finla\AppData\Local\ChessTK\analysis-tools\stockfish-19\stockfish\stockfish-windows-arm64-universal.exe`. Use finite reference searches as evidence, retain node budgets/PVs/history and deepen ambiguous positions. Offline labels and analysis are allowed under the last verified rules; shipping Stockfish, its code, published weights or a runtime answer store is not.

**Existing VPS:** authorized for this project, Linux x86_64, two vCPUs, 4 GB RAM, Python 3.12.3; runtime `$HOME/chess-tk/.venv/bin/python`, established staging base `$HOME/chess-sign-odin-20260905`. Reuse the established SSH connection/configuration or scoped prior project connection history; never guess usernames, expose credentials or put connection secrets in the repo. `systemd-run --user` with lingering was working for detached jobs. At last inspection the overnight jobs had finished; verify live activity before launching anything.

The VPS is the native signer and a small controlled test host, **not a large training farm**. At most two active CPU workers, one per core, with measured RAM headroom. Two comparison lanes can retain four agents only while total resident memory safely fits. Inspect and preserve collector/service states; do not start collectors into tests. No free pondering while an agent's opponent is running. Keep trustworthy one-core, 2 GiB timing measurements separate from deliberately concurrent throughput work. The signer's EPYC-Genoa is not the platform's EPYC 9V74; native measurements still have transfer uncertainty.

Actual submission archives must later be packed and tested on Linux. R&D transport archives are not approved submissions. Inspect CLI arguments and source before using old staging scripts: several freeze plans and finalizers are hardcoded to v5/v6 and must not run unchanged for Tempest.

## 7. Competition boundaries and feasibility

Re-fetch and timestamp the [agent contract](https://aichessathon.com/docs/agent-contract.md), [rules](https://aichessathon.com/docs/rules.md), [rendered docs](https://aichessathon.com/docs) and relevant [official starter](https://github.com/advitrocks9/aichessathon-starter) source. If a fetch fails, try an ordinary HTTP/rendered-page fallback and clearly identify cached facts. Live rules win over stale local prose.

Last verified limits: readable Python source; `agent.py` at ZIP root; `get_move(fen, time_left_ms)` returns legal UCI; Python 3.12; one EPYC 9V74 core at 2.60 GHz; 2 GB; no network or GPU; 90-second import; 120 seconds plus 0.5 seconds credited **after returning**; process persists for one game and is suspended on the opponent's turn; 50 MB uncompressed submission; writable `/tmp` limited to 256 MB and wiped between games. Referee automatic outcomes precede requests, with a **600 absolute-ply draw cap including the opening**. Old 60-second initialization and 300-ply material adjudication passages are obsolete.

Original JIT code and original trained weights are permitted under the last verified rules. Third-party engines, wrappers, translations, published networks and runtime engine-answer databases are prohibited. Evaluate any book/tablebase idea against the current wording and provenance rather than assuming permission or prohibition from an old development cut. Keep any proposed architecture inside the actual deployment envelope; heavy training libraries need not and ordinarily should not enter the submission. Creative liberty permits reconsidering earlier engineering tradeoffs, not circumventing competition rules.

Do not turn this into another generic reliability audit: the baseline has passed its gates. Investigate playing strength. For changes to move generation, state, search or deployment, specify and run the particular correctness checks they require, so a promising result remains credible.

## 8. Deliver an actionable research result

Maintain a short experiment ledger with hypotheses, source hashes, commands, data splits, budgets, results and negative findings. Give concise progress updates; continue useful independent work when a nonessential clarification is pending. Prefer a decisive small experiment to prolonged speculation.

Create:

1. **`docs/TEMPEST_RD_REPORT.md`** — evidence-backed current bottlenecks; comparative opponent findings with dated sources and uncertainty; executed experiments and reproducible results; rejected hypotheses; ranked opportunities.
2. **`docs/TEMPEST_BUILD_SPEC.md`** — one recommended Tempest architecture and one fallback. Specify concrete file/function changes, data/label generation, feature definitions or model shapes/dtypes where relevant, inference/update logic, training and quantization details if applicable, implementation order, dependencies, expected costs, tests and ablations. Distinguish measured components from proposals still requiring validation.
3. **`lab/tempest/`** — original research scripts/prototypes, manifests and compact result artifacts. Keep large or restricted source data appropriately separated, with provenance and reproduction instructions.

Rank the best three opportunities by likely competitive value, evidence strength, implementation effort, runtime cost and uncertainty. Recommend a coherent first build rather than bolting every idea together. If the evidence supports only a smaller gain, say so and explain the best next information-gathering step. Include a practical staged test plan against v6, wider playing-style guards, release gates and explicit rollback criteria. Aim to improve general strength; avoid teaching to the known test roots.

Your final response must be a **self-contained handoff the user can paste back to the implementation agent**: what you found; what the opponents demonstrably do better; what remains unknown; exactly what to build first and why; measured experimental results with denominators and budgets; artifact paths and reproduction commands; remaining tests and risks. Include enough technical specification to act without rerunning your research. Do not end with an offer to begin the investigation—you are to perform it now.
