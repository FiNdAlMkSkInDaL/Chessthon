# Compact null-history experiment

Candidate: `odin_history_compact/`, copied from frozen `odin_history_perf/` r2.
Only `core_nb.py` differs. Neither r2 nor main Odin was edited.

Local source snapshot: `odin-history-compact-source.zip`, SHA-256
`a02feaaf455add40e2dcf78e72c0da078414d5275efbe5081be42b2f559b79b1`.
This is experimental source for native staging, not a release recommendation.

The variant removes the additional `null_tree` parameter and its per-node
branches. At each actual null-pruning call it instead passes the unused history
suffix, zero prior length, `has_pair=False`, and a distinct `NULL_HIST_SEED`.
The null pass does not append a real game position. Its subtree behaves like a
fresh hypothetical game from the synthetic board: subsequent legal positions
can form virtual repetitions, and their TT scores use the virtual count context.
A nested null call starts another fresh virtual ledger. Normal consecutive-null,
sparse verification, real-edge cap and rule-50 policies are retained.

Before a zeroing move, equal real and virtual occurrence bags have distinct
score identities. After a legal pawn move or capture, none of either prior
ledger's boards can recur, so both reset to the ordinary empty-history context.
The future legal position, count bag, halfmove clock and cap distance then fully
determine the draw-rule context. Sharing scores there does not require knowing
whether an earlier discarded prefix contained a null pass. The earlier concern
that zeroing erases a namespace distinction is therefore not itself a correctness
counterexample. Both this author and the independent audit agent found no
counterexample to this model; the 64-bit context digest retains its normal
probabilistic collision limitation.

This is not asserted to produce identical scores to explicit-barrier r2:
r2 suppresses every synthetic repetition, whereas this variant recognizes legal
cycles after a virtual start and can reuse virtual-context TT bounds. NMP itself
remains a selective-search heuristic. Initialization cost, decision quality and
development games must determine whether this variant is useful.

`test_history_compact.py` passes eleven lightweight tests without Numba
compilation, adapting r2's nine tests and adding actual null-call execution for
real and nested-virtual caller histories, parent-prefix restoration and context
namespace checks. The legal queen-triangulation counterexample remains included.

`native_gate.py` is prepared for a one-core, 2-GiB Linux x86-64 Python 3.12 run
with `NUMBA_BOUNDSCHECK=1`. It checks actual compiled full/trimmed history, TT
context isolation, zeroing, long-history bounds, cap behavior and the legal
queen-triangulation null barrier. Native success and performance are pending;
no additional engine jobs were launched by this subtask.
