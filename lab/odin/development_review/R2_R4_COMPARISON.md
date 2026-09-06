# Windows development-root comparison: r2 and r4

Both sources were tested in fresh Python3.12 processes, pinned to laptop CPU4,
with library thread counts set to one. Full recorded move histories were replayed
and all legal roots retained. Before each root/budget, TT keys, move hints,
scores, depths, generations, history and killers were cleared. Soft and hard
targets were both the stated ceiling; the real adaptive controller could stop
earlier. Source hashes were unchanged before/after each worker.

| Source | Decision | Budget ms | Actual ms | Move | Depth | Score cp | Nodes |
|---|---|---:|---:|---|---:|---:|---:|
| r2 history/performance | 32 | 1000 | 857 | a4 | 8 | −57 | 74,025 |
| r2 history/performance | 32 | 3000 | 3013 | a4 | 8 | −57 | 287,744 |
| r2 history/performance | 33 | 1000 | 1001 | a5 | 6 | −57 | 101,376 |
| r2 history/performance | 33 | 3000 | 3010 | a5 | 7 | −68 | 278,528 |
| r4 compact guard | 32 | 1000 | 501 | a4 | 8 | −57 | 51,011 |
| r4 compact guard | 32 | 3000 | 1934 | a4 | 10 | −65 | 202,029 |
| r4 compact guard | 33 | 1000 | 516 | a5 | 7 | −68 | 56,535 |
| r4 compact guard | 33 | 3000 | 2035 | Be5 | 9 | −69 | 217,987 |

The known strategic error persists. At move32 both sources choose `a4`. At
move33, r4 changes its choice with the larger budget, but the resulting `Be5`
does not find the defensive resource `axb5`. A bounded Stockfish19 follow-up at
one million nodes per forced root gives **Be5 an upper bound of −358 cp** after
`...Rxh3`, while **axb5 is 0 cp** with no bound flag. This does not prove exact
endgame values, but the alternative remains a poor defence in the reference.

These positions therefore remain useful known weaknesses. The experiment
supports neither “more time solves the problem” nor an exclusive attribution
to the evaluator: search selectivity and iteration completion also differ.
Windows depths/timings cannot substitute for native Linux comparison or fresh
paired playing-strength evidence.

## Warmup discovery

Both original imports reported `NUMBA_READY=True` while the root dispatcher
had no nopython signature. The first r2 worker stopped on that invariant and its
stderr was retained. For the requested chess diagnosis, subsequent workers
performed an explicitly measured off-clock root compilation without modifying
source or readiness:

- r2: import29.012s, deferred root compilation133.303s.
- r4: import33.536s, deferred root compilation77.640s.

The table excludes those compilation times. This is not a valid competition
initialization result. The release controller was notified and assigned a
separate final warmup repair; neither tested r2 nor r4 was modified here.

Files: `odin_history_perf-critical-roots-windows-offclockwarm.json`,
`odin_compact_guard-critical-roots-windows-offclockwarm.json`, their stdout/stderr,
`r4-be5-reference.json`, and reproducible `compare_sources.py`/`assess_be5.py`.
All engine workers and the Stockfish follow-up exited; CPU4 is free.
