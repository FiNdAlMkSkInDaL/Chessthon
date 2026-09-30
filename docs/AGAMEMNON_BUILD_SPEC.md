# Agamemnon — next implementation contract

Read `AGAMEMNON_RESEARCH.md` and `lab/agamemnon/results.json` first. This is an
architecture generation, explicitly authorized by the user. Earlier local
prohibitions on neural experiments do not veto it; live competition rules do.
Tempest r1 remains the release and control. Do not silently overwrite old lab
sources, completed streams, signer archives or the official harness.

## Working assets

- `lab/agamemnon/representations.py`: original train/forward/gradient kernels,
  additive/NN/pair arms and three representation encodings.
- `chessbench_slice.py`: bounded, reproducible public training-data range reader.
  Attribution and byte-level provenance are recorded; original weights only.
- `public_data_prepare.py`, `public_train.py`, `transfer_train.py`: original
  scratch pretraining and controlled adaptation experiments. Existing directories
  are completed artifacts; parameterize new outputs before another run.
- `native-delta-r1/delta/`: working original incremental neural prototype,
  trained checkpoint derived from first seed 260906, width 32.
- `native-delta-r1/quant_refresh/`: identical quantized evaluator for search
  identity and cost comparisons. Both have Linux checks, not release certification.
- `policy_budget.py`: tested probability/depth math and development calibration.
  It is **not** wired into native search.
- `chessbench/block-18.bin` and `block-19.bin`: sealed raw records. Do not decode
  them for tuning. Existing twelve Tempest confirmation games remain unplayed.

## 1. Improve the training/search interface

Public pretraining helped all four tested architectures after adaptation. The
next bottleneck is representative search data and target quality, not importing
a bigger ML framework into the agent.

Use public data for volume and our own search for relevance. Sample quiet
quiescence leaves, critical siblings, queen-trade transitions, king-defence
positions and balanced material-imbalance endings. Retain original FEN, history,
source game/family where known, budget, teacher version, score perspective and
bound type. Never train fail-high/fail-low bounds as exact values.

Freeze new opening/game groups before labels and candidate selection. Public
positions lack game IDs: exact and mirror deduplication is possible, true
cross-corpus opening-family independence is not established. Use a separate
fresh decision/game benchmark and describe the distinction accurately.

Cross 32/64/128/256 widths with feasible 32k/128k/512k training levels. Compare
scalar residual, transformed-value or categorical value objectives, and phase/
material-specific heads. Use learning curves and tail diagnostics; don't add
epochs blindly when validation already worsens. Run at least two seeds.
Give each architecture comparable optimization effort before judging capacity.

Investigate CP calibration with a **separate** frozen calibration sample. The
observed 1.37 multiplier is not a universal constant to bake into the engine.
Separate calibration-only, pretraining-only and adaptation ablations. Measure
quiet and guard distributions separately. The current model's quiet/tail
regressions remain an explicit blocker to promotion.

The first 200k-record download took ~30 seconds; encoding took ~231 seconds.
Parallelize bounded CPU encoding and avoid repeated FEN/feature reconstruction
when scaling. Keep sources/manifest stable and compare numeric arrays exactly.

## 2. Extend and verify incremental inference

The current cache is exact for shared piece-square features: last-evaluated-board
set differences update integer sums. Preserve that invariant across arbitrary
jumps, skipped evaluations, null moves, promotions, castling and en passant.
Quantization at4096 incurred <0.49 CP maximum prediction change in this pilot.
Recalculate overflow and quantization bounds for every new checkpoint/width.

King-conditioned representations require refreshing/reindexing when context
changes. Relative geometry is not a free per-piece update after king movement.
Measure feature extraction, refresh frequency and whole search, not just vector
arithmetic. Pass learned numeric arrays explicitly through compiled recursion;
do not embed megabytes of learned constants into JIT code.

Gate: independent feature rebuild parity, make/unmake-equivalent transitions,
perft, source/reset isolation, quantized refresh/delta fixed-node identity, and
one-core Linux import plus wall-clock probes. A new evaluator can invalidate
pruning margins: test score scale and missed low-prior tactical refutations.

## 3. Build a policy that changes search allocation

Train on all relevant legal alternatives, including captures and promotions.
Collect soft preferences/margins and low-prior refutations. Existing4064 quiet
one-hot groups are a proxy only; one third of their teacher moves have below-
uniform learned probability. An action-value sample inspected from ChessBench
had interleaved positions, so don't assume contiguous records form full legal
move groups. Obtain complete small groups with bounded teacher analysis where
necessary, retaining bound/score provenance.

Reuse a shared board embedding; score from/to/promotion/action features without
running a whole network separately for each move. Begin with root and upper
nodes, where advisor cost can be repaid by avoiding descendant work.

Implement three otherwise identical controls: ordering-only; heuristic
probability budgets; learned calibrated probability budgets. Uniform probabilities
must reproduce the declared baseline depth allocation. Positive probability
floors do not constitute tactical verification. Keep compulsory shallow coverage,
check evasions, full-depth re-search after reduced fail-high and repetition/cap
handling. Measure regret and catastrophic misses, not just top-three prediction.

Gate: zero-prior/forced-move/extreme-logit tests, exact rule state, equal evaluator
and wall budgets, calibrated held-out decision targets, and policy overhead
included. Use geometric budgets0.1/0.5/2/8 seconds on a balanced used screening
suite; reserve fresh families for final selection.

## 4. Keep genuine architecture alternatives alive

Implement a small original graph/relational advisor only after measuring input
construction cost. Compare it to a flat/shared-embedding policy at equal label
compute and inference budget. Distil useful expensive advice into the cheap
model as a separate experiment.

For best-first minimax, maintain an explicit bounded frontier and verify leaves
with shallow AB/qsearch. Cross cheap and learned evaluators with AB and best-
first search: the old evaluator alone cannot establish best-first's ceiling.
Respect history-dependent draws; position-only DAG merging is insufficient.
Unknown/unproven tactical states must not be treated as solved wins or safety.

For a two-speed controller, compare an oracle gate, a learned gate, and equally
costly simple gates. Train from actual regret changes at multiple search budgets.
Measure value per added millisecond; score stability alone is not a stopping rule.

A small original policy/value MCTS or searchless model remains an exploratory
arm. It must demonstrate an attractive data/compute learning curve; published
GPU/TPU results are not our CPU performance measurements. No pretrained models
or third-party engine implementations enter a prototype or release.

## 5. Promotion and resources

Use the laptop's Python3.12 environment for four bounded one-thread fitting or
reference workers on CPUs2/4/6/8. The VPS has two cores and about4GB: at most two
active CPU lanes with enforced memory budgets, and no changes to unrelated
collectors. Current experiments are finished. Source transports are not release
archives; only the Linux signer may pack a final submission.

Do not nominate the current neural model from its mean error or selected game
positions. Require fresh decision evidence, quiet/tail behaviour and actual
full-clock games against Tempest under the current pinned referee. Complete the
chosen test plan regardless of a favorable running score. Do not spend112games
on every immature architecture; use that confirmation only after a concrete
candidate survives screening and deployment gates.

No training job, benchmark, reminder or overnight run is automatically pending
after this R&D cycle. No permission is needed to continue authorized development;
do not interpret this document as an approval checkpoint.
