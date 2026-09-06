# Sparse-NMP guard experiment

This isolated candidate starts from the frozen history-performance r2 source
ZIP `d9f4a18f1fa262fcb6170c281f3e7e937f73485409f4205020bf2cbd27b084a3`.
It preserves the explicit `null_tree` barrier and all other r2 changes.

The sole engine change is in `core_nb.py`: NMP additionally requires
`nmp_safe_nb(bb)`, and the expensive sparse-ending fail-high verification is
removed. Thus queen positions and positions with at least five non-pawn,
non-king pieces retain the existing NMP. Sparse queenless endings use the
ordinary selective search, including the existing RFP/IIR/LMR/SEE gates.
The change does not globally disable selectivity.

Reproduce with `build_sparse_guard.py`; inspect `against-history-r2.patch`.
Eleven modules remain byte-identical. The source-only test ZIP is
`odin-sparse-guard-source.zip`, SHA-256
`cb9fd5f5e18d9f11ab482948aa3775b5d625072b273c8cca1d2acda3b8553886`.
It is not a Linux release or a promotion recommendation.

All three lightweight tests pass. They execute the actual negamax branch with
controlled children on valid rich/sparse boards and both signs of beta, verify
that rich NMP and exact restoration survive while sparse NMP is never called,
and compare complete module ASTs after removing only the NMP branch. Every
other search gate is unchanged. These are source-body tests, not JIT results.

The release owner will measure the exact source on Linux against r2 and the
other candidates. No playing-strength or speed improvement is claimed before
those measurements and subsequent development games.
