# Odin pre-release source audit — 5 September 2026

This began as a read-only review of the local source snapshot with SHA-256
`64b9084d58e0f292ee7c61a6f09c2bcae31a2a2cc8bca544f18131018ce22dc6`.
The release owner subsequently authorized the bounded repairs recorded below.
It is not a native performance result or release approval. Initial findings
describe the bytes at the start of the release task. Machine-readable hashes and notes
are in `lab/odin/release_audit_notes.json`.

## Repairs and follow-up findings

1. **Sparse null verification has the wrong search window.** In
   `odin/core_nb.py`, `unmake_null` restores the original side to move, then
   the `verify = negamax_nb(...)` call searches `[-beta, -beta + 1]` with no
   negation. Its result is compared with the original `beta`. The real-position
   verification must search `[beta - 1, beta]`. A fail-low result from the
   current window is an upper bound, which must not be accepted as a proof
   that the position fails high at another threshold. Negative beta makes
   this particularly clear. Alternatively, disable null pruning in these
   sparse endings. The existing test only checks `nmp_safe_nb` classification;
   it does not exercise the verification branch or its bounds. **Repaired:**
   the window is now `[beta - 1, beta]`. The lightweight regression executes
   the actual negamax body through this branch with deterministic child
   results, both signs of beta and exact restoration. A separate two-level
   bound counterexample demonstrates why the negative-beta case was invalid.

2. **Correction to the initial fallback concern:** the outer iteration sets
   `_allow_abort = False`, but `_root_search` already sets it true before each
   root child. Thus the initial claim that all recursive fallback deadlines
   were disabled was incorrect. The outer assignment is now explicitly true
   for clarity. An actual Numba-unready tactical fallback at a 260 ms hard
   allowance aborts and restores the position exactly. No fallback flag defect
   or strength gain is claimed from this clarity change. The fallback's TT
   score cutoffs are also disabled by `_adjudicate = True` in the live entry
   path; it does not actually reuse its old position-only scores.

3. **False fifty-move draws after any historical pair.** The release owner's
   native probe found that the new `has_pair` call path invokes the fifty-claim
   helper even below 99 halfmoves. The helper lacked its own lower-bound guard
   and treated any continuing quiet move as claimable. **Repaired:** both
   native and Python helpers immediately return false below 99. Differential
   lightweight tests cover clocks 0, 5, 98, 99 and 100 against python-chess;
   an actual legal history that repeats once, then advances a pawn, no longer
   turns a material advantage into a fabricated draw. The release owner runs
   the separate compiled differential test over the broader corpus.

4. **Cap precedence at maximum recursive ply.** The search formerly returned
   static evaluation at ply 96 before checking the actual game cap. **Repaired:**
   native and fallback cap checks now precede the recursion guard. Native
   checking allocates its two small scratch arrays only on the rare cap-plus-
   maximum-ply boundary, preventing an out-of-bounds access. Lightweight tests
   exercise the actual function bodies at ply 96 for a valid mate and a draw.

All seven tests in `lab/odin/test_release_repairs.py` pass without JIT. They
exercise real source bodies with controlled dependencies where appropriate,
plus actual Python search. They do not substitute for the exact compiled
archive gates. Two old cap-mate fixtures containing two black kings were also
replaced with `8/8/8/8/8/k7/2q5/K7 b - - 0 300` and validity assertions.

## The existing control does not isolate the mandatory rules repair

`storm_rules600_control/` is already a broad rules/search-corrected engine.
Against the original Storm archive it contains legal SEE, canonical EP keys,
threefold claim search, full history-sensitive TT identities, removal of the
root deletion filter, one-sided aspiration retries and root-work accounting,
as well as the cap, buffer and clock repair. The build brief explicitly asked
for the control immediately after its first, mandatory cap/buffer stage.

Nine of the twelve modules are text-identical between this control and Odin.
The other three are:

- `agent.py`: comments only.
- `eval_nb.py`: unused fitted feature functions/constants and comments;
  `evaluate()` still uses vanilla PeSTO.
- `core_nb.py`: sparse-null fail-high verification, additional telemetry and
  unreachable fitted evaluator functions. `evaluate_nb()` still uses PeSTO.

An 80-game match against this control would therefore predominantly test the
sparse-null verification change. It must not be described as measuring the
complete Odin foundation against minimally rules-corrected Storm. The release
owner requested a new minimal control. It is now available separately as
`storm_rules600_release_control/`, reproduced directly from the exact Storm
archive. See `docs/ODIN_MINIMAL_CONTROL.md`. The old control is preserved.

## Performance questions for the native gate

The TT signature is order-sensitive and covers the entire recorded game plus
the searched path; it does not reset after an irreversible move. Both score
lookup and hash-move ordering use that contextual key. This protects score
validity, but prevents reuse between ordinary transpositions reached through
different move orders. A separate position-only move hint can be safe when
validated against the current legal/generated moves; a position-only score
cannot replace the contextual score without a separate correctness argument.

Once any position has appeared twice, `has_pair` remains true in all later
searches, even after captures and pawn moves. Each affected node generates all
legal moves and scans prospective repetitions across the full history. Test
late-game histories as well as fresh middlegame roots before assuming adequate
native search throughput. A rigorously bounded reversible-history window could
reduce this work, but must preserve prospective claims and cap semantics.

The unreachable native fitted helpers reference undefined `FILE_M`, `FEAT_MG`
and `FEAT_EG`; calling them would fail compilation. `USE_FITTED_EVAL = True` is
also misleading because neither actual evaluator calls the fitted correction.
Keep the experiment disabled and remove or clearly quarantine these remnants
before a final freeze. No fitted evaluation strength gain is established.

## Positive observations and scope limits

Legal SEE explicitly checks trial king safety, pins, promotions and en passant
occupancy. Real history allocation has maximum-recursion slack. The cap uses
the FEN's absolute ply and advances only on legal search edges. The normal
legal-path TT score identity includes history, halfmove clock and cap distance.
Warmup and runtime use consistent history and deadline array dtypes. Root
legal-firewall and panic paths are retained.

These observations do not replace native perft, protocol, cold-import,
deadline, bounds-check or strength gates. The historical referee and official
Storm archive were not edited. Only lightweight local tests were run by this
audit subtask; the release owner controls native validation and match jobs.
