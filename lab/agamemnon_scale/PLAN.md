# Agamemnon scale cycle 1

Authorized 6 September 2026. Preserve Tempest r1 and all earlier experiment files.

Acquire 112 nonoverlapping 10,000-record blocks from ChessBench TRAIN, excluding
all earlier sampled ranges. Reuse the declared public development blocks; sealed
blocks and fresh match families remain unopened. Deduplicate exact and mirrored
positions against development and the old search-state corpus. Missing game IDs
prevent a claim of opening-family independence. Keep public CP calibration
unchanged in this scaling experiment, so dataset size is the changing variable.

Train original additive, width32, width128 and width256 models on nested 128k,
512k and 1m subsets, two seeds, eight epochs. Same targets/optimizer; retain each
curve. Adapt each pretrained checkpoint for 45 epochs on the existing search-state
training families, select checkpoints on reused development error, report quiet,
guard and endgame tails. These are development results, not independent Elo.

Separately label 512 public roots (384 training,128 development) with all legal
alternatives using an offline original-label pipeline and Stockfish19 MultiPV,
64k nodes per root. Record scores, bounds, mate values, nodes, depth and full move
coverage. Train soft preferences from value margins, not one-hot moves. Native
integration uses upper-tree learned reduction allocation, mandatory minimum depth
and full-depth fail-high re-search. Compare allocation versus ordering-only and
the identical evaluator without policy. Preserve tactical exemptions and rules.

Gates: encoder parity, gradient/colour checks, complete label coverage, calibration
and regret, quantized accumulator parity, perft, Linux cold import, ABA state reset,
bounded node/wall probes and paired development matches. No Desktop promotion
without independent strength and current-referee protocol gates. Scaling is finite
and measured; a million rows is a stage, not a claim of unlimited improvement.
