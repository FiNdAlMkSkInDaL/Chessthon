# Independent release-tool agent search review

This read-only review inspected `odin/core_nb.py` after the primary audit's
sparse-null-window and fifty-claim guards were corrected. No engine source was
edited by this reviewer.

## Confirmed null-history boundary issue

The internal null search passes the real `hist`, `hlen`, `has_pair` and
`hist_sig` into its imaginary position. A real, legal trace can contain the
opposite-side version of the current board twice without any current claim.
The null child then recognizes a third occurrence, even though no legal move
was made. This is a search-state defect; the example below does not by itself
prove a changed or losing root choice.

Start:

`3q3k/8/8/8/8/8/8/K2Q4 b - - 0 1`

Trace:

```text
h8g8 a1b1 g8g7 b1a1 g7h8
a1b1 h8g8 b1b2 g8h8 b2a1
h8h7 a1a2 h7g8 a2a1 g8h8
```

All 16 real positions are valid and `board.outcome(claim_draw=True)` is `None`
throughout. Final root:

`3q3k/8/8/8/8/8/8/K2Q4 w - - 15 9`

The board with Black to move occurred at the start and after ply 10. A null
from this root changes only the relevant side/EP key and matches those two
real-history entries. `count_key(...) >= 2` therefore returns a fictitious
draw. Queens are present, so Odin's `nmp_safe_nb` permits the ordinary null
path. The primary audit received this fixture for correction and regression.

A sound correction must isolate pre-null repetition context while preserving
the parent history after return; simply passing `hlen=0` against the same
array allows descendants to overwrite the parent's prefix. It must also keep
imaginary history out of score-TT contexts and preserve legal post-null cycle
handling according to the chosen null-search approximation.

## Recursion bound before terminal semantics

Both native qsearch and negamax returned PeSTO at `ply >= MAX_PLY` (96) before
checking `cap_left <= 0`. Thus a cap leaf reached at the recursion bound could
receive a nonzero heuristic score instead of the referee's draw, or miss mate
precedence. This is a rare correctness edge: the regular depth limit is lower,
but extensions/qsearch can reach the recursion bound. The primary audit was
notified. A repair must not index `stacks[96]` or `undos[96]`; bounded terminal
generation needs separate scratch storage or an equivalent safe guard.

## Paths inspected without an additional confirmed defect

- Reduced alpha improvements receive a full-depth verification before trust.
- Every visible recursive legal make and null make is undone before an abort
  is propagated. Histories allocate room for the prior prefix plus recursion.
- Rule-50 intended quiet claims check that the child has a legal continuation;
  immediate mate/stalemate precedes the claim predicate.
- Mate TT normalization adds/subtracts the native recursion ply symmetrically.
- The legal SEE trial removes the victim and validates the recapturer's king.

These statements are scoped code-review observations, not a claim of exhaustive
search correctness. Native perft, actual-source rule differential, short-clock
stress and the frozen paired matches remain the release evidence.

## Oracle trace preflight

The separately authorized review of `lab/odin/native_release/rule_differential.py`
added a no-engine `--oracle-only` mode. It verified 66 traces, 3,857 legal
positions, all 37 exact retained diagnostic endpoints and eight claimable
positions. Its mutable native arrays are copied before each comparison, and
legal move output is separate from the scratch used by rule-50 exploration.
Some traces deliberately continue after automatic claimability to exercise the
predicate boundaries; they are legal-position histories, not purported complete
competition games. The native differential itself still must be run by the
release controller.
