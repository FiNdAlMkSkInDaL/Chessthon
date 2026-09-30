# Agamemnon scaling — completed R&D cycle

Completed6 September2026. User authorized large-scale pretraining, incremental learned
evaluation and learned branch allocation, then explicitly requested more training
while the learning curve improves. This is an implementation and experiment cycle.
the signer archive (not in git) remains Tempest r1, SHA256
`0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4`.

## Completed evidence

- Acquired112 new ChessBench TRAIN blocks,1.12m raw records.1,065,323 filtered,
  exact/mirror-deduplicated training positions;19,020 reused public development
  states. Original public sealed blocks and fresh match openings untouched.
  Data has no game IDs; no family-independence claim across public corpora.
- Original contiguous sparse-gradient kernel matches original gradients exactly
  on tested32/128/256 widths. Local kernel speedups about2.7–3.5x. Entire neural
  training has no Torch dependency; original NumPy/Numba kernels and parameters.
- Four model widths1/32/128/256, nested128k/512k/1m data, two seeds, eight epochs;
  each pretrained checkpoint received45-epoch search-state adaptation. All curves
  are retained, with checkpoint selection on reused development only.
- Width32 adapted development MAE:128k272.04/268.74;512k240.81/242.95;
  1m230.94/232.04. Tempest272.50 on the same states. Quiet and endgame errors
  improved as well. Larger widths have not shown a consistent capacity advantage.
- Compute control:125k unique rows x64 epochs versus1m x8 gives8m examples in
  each arm, optimizer updates31296 versus31256. Adapted125k errors261.23/257.55;
  the1m result is better beyond merely doing more optimizer updates.
- Width32 first-seed1m checkpoint integrated into exact integer lazy-delta
  evaluator. Linux cold34.949s;6 perft positions,5288 accumulator/evaluation
  parity positions, ABA reset, fixed-node and equal-wall diagnostics passed.
- Completed16 paired500ms development games against Tempest:5W/1D/10L,34.375%.
  All games completed legally. This rejects that checkpoint for promotion and
  demonstrates why lower static error is not sufficient playing-strength evidence.

## Learned allocation

An original128-coefficient conditional policy uses32 basic move/value features
and piece-conditioned interactions, including the incremental neural evaluation
change. Full legal alternatives are labelled on512 fixed public roots,384 train
and128 development,14,836 moves. Labels use independent16k-node forced-move
searches with cleared hash. Latest complete unbounded score-bearing PV is retained
from the streaming analysis API. They are finite search estimates, not exact
minimax values. Published engines are OFFLINE teachers only and never ship.

Two initial label-collection attempts are preserved. Aggregated analysis dictionaries
retain old bound flags (`AnalysisResult.post` uses dictionary.update). Naively
excluding every group with any such flag retained only223 and94 groups. Those
fits are rejected and superseded by the streaming512-group collection.

Policy development crossentropy2.911 versus uniform3.180; top-choice CP regret
456.93 versus neural-only453.93 and PeSTO467.68. This modest policy signal does
not establish a strength gain. About35% of teacher-best moves have below-uniform
prior probability. Do not treat this policy as reliable enough to prune blindly.

Native upper-tree policy runs at depth>=5, retains TT/tactical/killer ordering
precedence and changes other quiet ordering. The allocation arm converts
probability into quiet reduction depth, retaining at least two child plies and
all existing tactical exemptions. Reduced fail-highs are verified at full depth.
The ordering-only arm isolates allocation; a uniform allocator source is retained
for a subsequent ablation. Counters prove real allocation/re-search activity.

The advisor variant retains Tempest's leaf evaluator and uses the learned model
only for policy features, separating search guidance from leaf-score replacement.
Both advisor ordering and allocation passed Linux cold/perft/5288 neural-state
checks, policy feature parity and ABA diagnostics. Cold times34.987/34.945s.
The16-game allocation-versus-ordering development match completed6W/5D/5L,
53.125%. A subsequent16-game advisor-versus-Tempest screen finished5W/6D/5L,
50%. Neither establishes a strength gain.

## Four-million expansion and turn-aware heads

`lab/agamemnon_scale/data.py --directory data-r2 --blocks320 --include data`
added3.2m raw records to the existing corpus, excluding all earlier record ranges
and deduplicating against existing data/development. Four acquisition/encoding
workers, shared memory-mapped numeric training arrays. It completed with4,106,090
training rows. Initial and expansion sources are preserved as`data-r1-source.py`
and`data-r2-source.py`; the current reusable reader additionally fixes CPU
assignment to worker identity rather than block number, avoiding collisions
between variable-duration jobs. All previous artifacts remain intact.

After acquisition, `train_more.py --seed 260908 --cpu 2` and the corresponding
seed260909/cpu3 runs continued width32 from each1m PUBLIC checkpoint on4m unique
rows for8 epochs at0.0007, then adapt45 epochs at0.001. Adam moments restart;
this is weight continuation, not exact optimizer resumption. Both seeds completed:
public MAE134.54/134.16, adapted226.38/228.79. Best public epochs4/5; further
passes were worse. Each run processed32m additional training examples.

Further inspection found an architectural limitation: the old learned correction
was independent of side to move. The search already alternates sides correctly;
only its learned evaluator assumed a fixed tempo effect. `turn_model.py` adds
separate mover/opponent output heads on the SAME shared incremental features.
Colour-and-turn mirror symmetry, original-function initialization identity and
finite-difference gradients pass. Input turn is reconstructed exactly from cached
PeSTO plus/minus10 tempo, with a strict check, rather than inferred from labels.

The two turn-aware runs score127.68/127.94 public and214.88/214.71 adapted MAE.
Same-data, same-update antisymmetric-head controls score132.89/132.92 public and
225.05/227.01 adapted. These are reused-development error comparisons, not Elo.
The native773x32 packed model retains the exact integer accumulator; output heads
read the actual side to move at every simulated position, including null moves.
The native head passed Linux cold34.998s,6 perft positions,5288 exact integer
accumulator/evaluation checks, ABA reset and fixed-node/wall diagnostics.
Its16-game screen against Tempest finished3W/7D/6L,40.625%, so it is unpromoted.

The process is suspended during the real opponent turn. That does not make
turn-aware evaluation redundant: searches conducted on our clock evaluate both
sides' simulated turns. Existing TT entries persist between our actual moves;
this reuses completed calculations, not background thinking.

## Completed playing evidence

Every comparison completed its predeclared16 games on8 used opening families,
both colours,500ms maximum search allowance per move, one active mover per CPU.
These are development screens, not independent full-clock Elo measurements.

| Candidate | Control | W / D / L | Score |
|---|---|---|---|
|1m neural leaf evaluator|Tempest r1|5 /1 /10|34.375%|
|4m neural leaf evaluator|1m neural leaf evaluator|5 /8 /3|56.25%|
|1m learned allocation advisor|Same advisor, ordering only|6 /5 /5|53.125%|
|1m learned allocation advisor|Tempest r1|5 /6 /5|50%|
|4m learned allocation advisor|Tempest r1|2 /7 /7|34.375%|
|4m turn-aware neural leaf evaluator|Tempest r1|3 /7 /6|40.625%|

Total96 completed games,12,780 legal plies; no operational game failures.
Paired bootstrap intervals are recorded in`lab/agamemnon_scale/results.json`.
The small positive4m-versus1m result is inconclusive. None of the candidates
demonstrated superiority to Tempest sufficient to enter promotion confirmation.
The initial56 value fits plus8 turn-aware/control fits total64 completed value
model fits. Policy fits and failed/pilot collections are separately preserved.

The reusable public reader now checks a completed cache's hashes and returns
without rewriting it. Its4,106,090-row cache passed this resumption audit.
All local training jobs and Agamemnon VPS experiment services have completed.
No112-game overnight job, new automation, site upload or archive replacement
was created. The original sealed public blocks and12 fresh confirmation opening
families remain unconsumed. Round41's Alien Gambit win is present in the repo;
it was not used for this cycle's fitting or checkpoint selection.

## Next implementation priorities

1. Keep the efficient original training/incremental platform. Public pretraining
   and turn-aware heads are supported by prediction evidence, not yet by strength.
2. Collect states actually evaluated during this engine's search, including quiet
   leaves, checking/evasion states and optimistic losing branches. Split whole
   root families before labels. Offline-teacher targets must preserve score
   perspective, bounds, budget and available history. Test decision regret and
   tactical tails, not only aggregate CP error. Search can select rare evaluation
   mistakes even when the average prediction is better.
3. Test richer original king-relative/shared contextual features on the existing
   corpus. Width alone did not provide a consistent gain. Refresh the affected
   king-relative view on king moves; keep integer update/parity and Linux cost
   gates. This is a proposed next experiment, not implemented in this cycle.
4. Train/calibrate branch preferences on actual search alternatives and
   low-prior refutations. The512-root policy does not reliably improve teacher
   regret, and better crossentropy did not translate monotonically into strength.
   Retain uniform and ordering-only ablations; no blind probability pruning.
5. Gate against Tempest after each architectural nomination. Expanding public data
   can remain part of the pipeline, but MAE alone must not trigger promotion or
   be described as unlimited playing-strength potential.

## Exact locations

Core files:

- `lab/agamemnon_scale/PLAN.md`, `data/manifest.json`, `data-r2/plan.json`
- `train.py`, `train/lane*/results.jsonl`, `compute-control/results.jsonl`
- `policy-exact/plan.json`, `labels-*.jsonl`, `scaled-r1/result.json`
- `native-value-r1/`, `native-advisor-r1/`, `policy_native.txt`, `stage.py`
- `match-value-r1/lane*.jsonl`, `match-allocation-r1/`
- `value-match-review/`: finite diagnostic teacher review of both players at
  predetermined plies12/24/48/72. Mate-scale error dominates raw averages; these
  sparse, shallow teacher checks must not override the actual completed match.

VPS source roots are under `$HOME/chess-sign-odin-20260905/`, named
`agamemnon-scale-value-r1`, `agamemnon-scale-advisor-r1`,
`agamemnon-scale-match-value-r1`, `agamemnon-scale-match-allocation-r1`.
No credentials are stored here. At most two active CPU lanes,1 thread each,
1800MB service cap and no swap per lane. These are bounded research services,
not the complete no-network competition sandbox or a release certification.

Release requires current-referee protocol/init/resource gates and independent
strength confirmation. No public-model weights, reference engine, labelled
position lookup or training data may enter the submission.
