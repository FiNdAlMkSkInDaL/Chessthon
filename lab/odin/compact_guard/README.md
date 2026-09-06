# Compact history plus sparse-NMP guard

This isolated candidate combines the frozen compact null-history policy
(`a02feaaf455add40e2dcf78e72c0da078414d5275efbe5081be42b2f559b79b1`)
with the bounded sparse NMP guard already tested independently.

Only `core_nb.py` differs from compact alone. NMP additionally requires
`nmp_safe_nb(bb)`; sparse queenless endings no longer run the expensive
depth-minus-one verification with all aggressive pruning disabled. Rich
positions retain the original NMP and its compact history barrier. All other
search gates and eleven modules remain unchanged.

Reproduce using `build_compact_guard.py`; inspect
`against-history-compact.patch` and `manifest.json`. The local source-only ZIP
is `odin-compact-guard-source.zip`, SHA-256
`8d7a0284b2afad0d36ce628e50ae1a7f8ef6fd15469c04907452501918ea4897`.
It is not an approved release archive.

All fourteen lightweight tests pass: three actual rich/sparse NMP branch and
unchanged-other-gate checks in `test_compact_guard.py`, plus eleven compact
history, multiplicity, TT isolation, null-barrier and parent-prefix checks in
`test_compact_history.py`. These execute source bodies with controlled native
dependencies and real Python fallback searches; no Numba compilation occurs.
The copied history suite differs only in its source directory and output path.

The release owner runs native performance and operational gates and chooses
the development candidate using measured results. No speed or playing-strength
claim is made by this source snapshot.
