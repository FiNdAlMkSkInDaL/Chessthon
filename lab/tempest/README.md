# Tempest R&D evidence

Read `docs/TEMPEST_RD_REPORT.md` and `docs/TEMPEST_BUILD_SPEC.md` in the workspace root. No submission or promotion was produced. Everything in this directory is offline research; **do not package it with the engine**.

## Reproduce without overwriting evidence

From the Chess TK workspace, run:

```powershell
& '.\lab\tempest\reproduce.ps1'
```

This creates a new sibling `lab/tempest_repro_TIMESTAMP/`, copies scripts and the frozen public snapshots, and reruns the research sequentially. It refuses an existing output directory. It uses `C:\Users\finla\AppData\Local\ChessTK\venv312\Scripts\python.exe` and the authorized local Stockfish 19 ARM64 binary. It requires the unchanged `odin_v6/`, prior Odin lab helpers, original quiet labels/matrix/weights and release/game evidence still in this workspace. No network is required when all saved snapshots are present. Fresh public acquisition is a distinct operation (`acquire.py` in a new sibling research directory), because the site has moved on.

The original runs used independent CPU-affined workers: search 4, reference 6, extra search/model experiments 8. Reproduction is sequential to avoid timing contention. Node-budget results should be compared on move, completed depth, score and node count; exact wall times and wall-budget choices can vary. Python 3.14 is not the runtime of record. Local ARM results are not Linux deployment compliance.

To regenerate summaries only, preserving raw data:

```powershell
& 'C:\Users\finla\AppData\Local\ChessTK\venv312\Scripts\python.exe' -B '.\lab\tempest\summarize.py'
& 'C:\Users\finla\AppData\Local\ChessTK\venv312\Scripts\python.exe' -B '.\lab\tempest\finalize.py'
```

Individual bounded commands used in the original output directory (most outputs use exclusive creation; use the reproduction directory for another run):

```powershell
$py = 'C:\Users\finla\AppData\Local\ChessTK\venv312\Scripts\python.exe'
& $py -B lab/tempest/acquire.py
& $py -B lab/tempest/prepare.py
& $py -B lab/tempest/run_probes.py
& $py -B lab/tempest/reference.py --mode corpus
& $py -B lab/tempest/reference.py --mode games
& $py -B lab/tempest/probe.py --variant baseline --deep --cpu 8 --output lab/tempest/baseline-deep-probes.jsonl
& $py -B lab/tempest/public_deep.py
& $py -B lab/tempest/prepare_critical.py
& $py -B lab/tempest/probe.py --variant baseline --cpu 8 --cases lab/tempest/opponent-critical.json --output lab/tempest/opponent-critical-probes.jsonl
& $py -B lab/tempest/reference.py --mode choices
& $py -B lab/tempest/eval_experiment.py
& $py -B lab/tempest/label_audit.py
& $py -B lab/tempest/accumulator.py
& $py -B lab/tempest/public_audit.py
& $py -B lab/tempest/rule_probe.py
& $py -B lab/tempest/history_audit.py
& $py -B lab/tempest/freeze_confirmation.py
```

`reference.py --mode choices` is resumable. The first pass scored the completed early variants; the second filled late variant/actual/opponent moves. Metadata records each script version; rows are retained. It uses 1M-node restricted reference searches, not the earlier 300k-node played-move corpus screen. The finalizer requires every measured/actual candidate to have a reference row.

## Evidence map

- `identity.json`: release/archive identity, per-module hashes, baseline AST identity and own-game inventory.
- `experiment-plan.json`, `corpus-v1.json`, `split-manifest.json`: original predeclared six-variant plan and grouped discovery corpus.
- `prototypes/`: six isolated v6-derived policy/evaluation variants. Baseline core has normalized line endings, with AST identity verified. No original release source changed.
- `*-probes.jsonl`: native readiness, source/driver hashes, A–B–A, static rankings, completed-iteration traces and legal choices. Eight workers, including deep and opponent probes, each reset native state. Their root calls are not full-clock games.
- `reference-corpus.jsonl`: 1M unrestricted and 300k played-move first reference pass, discovery only.
- `reference-choices.jsonl`: 1M same-root forced reference for all candidate moves used in final comparisons. Complete available PGN history, single SF thread, 64 MB cleared hash.
- `reference-games.jsonl`, `public-deep.jsonl`: 1,330 shallow public move screens and 19 deepened consequential cases; all original estimates/PVs retained.
- `opponent-critical*.json*`: 12 targeted opposing turns around known Day 3 errors, and v6 reproductions.
- `eval-relations/`: four original ridge/Huber trials, coefficients, predictions and frozen split. Reused validation is not blind.
- `label-audit*.json*`: 120 preselected labels reanalysed at 1M nodes; FEN-only history limitation explicit.
- `accumulator*`: original integer-update prototype using our previously trained weights; no full evaluator integration.
- `public/`: public HTML/PGN snapshots, URL/date/hash manifest and team/game ID provenance. PGNs include clock comments. These are public observations, not guaranteed archive/version identities. The 24 saved games are nonvoid final results at both retrievals.
- `public-audit.json`: first audit using the legacy intended-move predicate; `rule-probe.json` supplies the corrected current-rule interpretation.
- `history-audit.json`: all 112 old release games replayed; old results preserved even where the new referee would continue.
- `fresh-confirmation/`: twelve balanced, unused opening families, candidate blind. Only starting-balance references exist; no engine results. Do not use the initial public reservations as a certified release holdout.
- `summary.json`, `tables.md`, `opponent-critical-summary.json`, `validation.json`: regenerated final summaries/consistency checks.
- `match/plan.json`, `match/games.jsonl`, `match/summary.json`: predeclared PeSTO-only follow-up, real get_move/reset workers and current-rule replay audit; 4W/1D/7L, not a release gate.
- `artifact-manifest.json`: checksums and sizes for reproducible scripts and compact evidence. Public HTML/PGN bytes have their own fetch/game manifests. Docs are hashed separately in the manifest.

Derivative stdout/stderr progress streams are preserved but excluded from the checksum manifest; the flushed JSONL records and source manifests are authoritative. The reproduction PowerShell script passed parser validation; the full second multi-minute research run was not executed merely to recheck orchestration.

## Experiment ledger

| ID | Hypothesis / intervention | Budget and split | Outcome / decision |
|---|---|---|---|
| T01 | Opponents have distinctive inaccessible strong moves | 24 public games; 14 discovery games, 1,330 50k+50k comparisons; 19 cases at 2M+2M | Several practical strengths observed; private architecture unidentified; shallow accusations sometimes disappear. |
| T02 | One broad pruning family is the bottleneck | Six variants, 24 focus roots × 200k/1M nodes/1.5s; baseline 30 extra roots | All variants reported; no justified blanket removal. Final paired metrics in tables.md. |
| T03 | More search / root ordering alone fixes the known errors | Eight 4M searches plus 17 forced 1M alternatives | Some corrections, persistent misranking in others. Subtree search/evaluation remains implicated. |
| T04 | Opponent exploitation itself is inaccessible | 12 opposing turns × three budgets | V6 matches 6/12 at 200k, 7/12 at 1M and 6/12 at 1.5s. All four adashima resources reproduced. |
| T05 | Added relational features outperform the old evaluator | 4,247 train / 1,354 reused validation; four ridge settings | Float MAE 96.83, int32 97.00 vs 97.24; p90 worsens. Reject deployment. |
| T06 | Labels/phase coverage limit learning | 120 labels, 40 per phase, 1M reference nodes each | Mean absolute drift 29.2cp; 17 ≥50cp, 7 ≥100cp. More data alone is not a demonstrated cure. |
| T07 | Incremental original representation is feasible | 2,999 state checks; 2 × 599,800 timed transitions per method | Exact updates/undo; ~1.78× isolated update-v-refresh ratio. Integrated cost/strength unmeasured. |
| T08 | Historical draw doctrine still matches the site | Exact new starter, five predicates, 24 public games, 112 old match games | Source changed; all 63 old repetition/fifty end positions still live now. Do not relabel old games. |
| T09 | Fresh confirmation can remain separate | 12 balanced starts, 4 e4/4 d4/4 flank; excluded prior families/transpositions | Frozen and unsearched by either engine; not a decisive promotion sample. |
| T10 | PeSTO-only root improvement survives play | Predeclared 12 games / 6 used development pairs, 100ms per move, exact v6 baseline, current referee | 4W/1D/7L,37.5%;1,352 legal plies replayed. Reject removal of fitted evaluation. |
| T11 | Broad opponent advantages survive deeper reference | All three qualifying ms/adashima roots; 2M unrestricted and 2M for each compared move | bxc5 advantage72cp; Qc1 narrows to19cp; Rf1 difference141cp in an already winning, reference-unstable position. |

Only PeSTO-only earned a cheap match from its selected-root improvement; it failed that follow-up. No full-clock game, Linux cold import, NN integration, persistent-game clock policy, tablebase deployment or release promotion was attempted. Those are explicitly staged implementation gates, not silently claimed completed work.

Setup-only errors were corrected before evidence runs: missing optional `psutil` used for inventory (replaced with native Windows inventory); a typo in a one-off diff command; default text decoding while checking scoped session connection history (retried UTF-8, no target recovered). Some requested web-tool pages failed; public HTTP snapshots succeeded. Empty stdout/stderr files can accompany successful explicitly flushed JSONL results. No failed game or probe was dropped from a result.
