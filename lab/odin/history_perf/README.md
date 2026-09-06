# Odin reversible-history and move-ordering experiment

The isolated candidate is `odin_history_perf/`. Main `odin/`, the controls,
and official Storm archives were not edited by this work. The source snapshot
is `odin-history-perf-source.zip`, SHA-256
`d9f4a18f1fa262fcb6170c281f3e7e937f73485409f4205020bf2cbd27b084a3`.
This is a local source snapshot, not a Linux release recommendation.

`against-fixed-odin.patch` is the exact difference from main Odin after its
release audit repairs. Only `core_nb.py`, `history.py` and `search_nb.py`
differ. The source includes the audit's fifty-claim `<99` guard, same-side
null verification window and cap-before-maximum-stack-depth terminal ordering.

## Changes and reasoning

1. Recorded served/played keys clear on a pawn move or capture, as indicated
   by the FEN halfmove clock. This does not infer an opponent UCI. Native and
   fallback roots also retain only the known preceding keys within that clock.
   Earlier boards cannot recur after a zeroing move. Castling-right losses are
   not used for additional trimming; retaining those unreachable keys is safe.
2. Each native legal zeroing child rebases its history array into the unused
   suffix, sets the prior length to zero, clears `has_pair`, and resets the
   context digest. This keeps a stale pair from triggering expensive legal
   intended-move scans in every subsequent node. The caller's prefix is never
   overwritten. The fallback uses a new empty list at the same boundary.
3. The history signature becomes an order-independent sum of mixed 64-bit
   position keys. Occurrence multiplicities remain significant; XOR alone
   would cancel doubles and is not used. Future repetition claims depend on
   this multiset, not its order. Score identity still combines the board,
   reversible history, halfmove clock and cap distance. Like the pre-existing
   Zobrist key, this is a probabilistic hash, not a collision-free proof.
4. A separate 262,144-entry move-only table occupies a 3 MiB tail of the
   existing key/move arrays. Full board-key matching is required. It supplies
   only move ordering (including the root/panic legal filter); no score, depth
   or bound can be read from that tail. The contextual score table is unchanged.
5. An explicit `null_tree` flag isolates an artificial null subtree. On entry
   the history view rebases to the unused suffix; no synthetic descendant
   appends history, claims repetition from the real history, or probes/stores
   contextual score TT bounds. The flag survives pawn/capture resets, qsearch,
   depth retries and nested null moves. Verification in the real parent keeps
   that parent's status. Existing legal-edge cap/fifty counters, ordinary
   terminal detection, pruning gates and board-only move hints are retained.

The null barrier fixes a concrete legal queen-triangulation trace whose
synthetic null board otherwise matches two recorded real positions and returns
a fabricated repetition draw. A seed-only separation was considered insufficient
for this implementation because zeroing resets would erase that distinction.

## Gates

`test_history_perf.py` passes nine lightweight tests in approximately half a
second. It imports no agent and performs no Numba compilation. It executes
actual extracted native function bodies, real history/fallback code, and
python-chess legal traces. Coverage includes:

- Signature permutations, multiplicities and fixed random collision sample.
- Score-context isolation with move-only reuse and forced hint-index collision.
- Root trimming, recorded repetition then own/opponent pawn moves, and exact
  draw-claim agreement with python-chess before and after zeroing.
- Actual qsearch/negamax entry rebasing, unchanged parent history, fallback
  full-history versus trimmed equivalence, and null score-TT exclusion.
- The legal queen-triangulation fixture and an actual recursive qsearch call
  through a legal zeroing child which must retain `null_tree=True`.

`native_gate.py` is prepared for the signer with `NUMBA_BOUNDSCHECK=1`, one
Linux x86-64 core, Python 3.12 and the normal 2 GiB resource envelope. It warms
the exact source, runs actual compiled contextual TT, legal zeroing-child,
long-history, cap/stack and null-triangulation checks, and reports hashes.
Native results are not claimed until that gate completes. Follow it with the
existing fixed-wall diagnostic performance probe and separate development
games before considering a final holdout.

No throughput, initialization-time, Elo or playing-strength gain has yet been
established for this experiment. In particular, move-ordering changes can alter
selective search behavior; nominal depth alone is not an equivalence test.
