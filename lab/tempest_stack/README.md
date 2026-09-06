# Compounding Tempest experiments

Read `docs/TEMPEST_COMPOUNDING_PLAN.md` at the workspace root.

- `stage.py`: frozen four-arm source generator, plan and allowlisted transport.
- `prototypes/narrow`: exact earlier pawn-LMR candidate.
- `prototypes/lazy`, `packed`, `both`: isolated, unpromoted optimizations.
- `bench.py`: identical fixed-node search, sort, perft and restoration checks.
- `plan.json`, `cases.json`, `launch.sh`: predeclared two-core mirrored-order run.
- Eight `*-a.jsonl` / `*-b.jsonl` files and lane logs: all completed Linux runs.
- `analyse.py`, `result.json`: source/driver identity audit and timing analysis.

All checks passed. Lazy predicate timing improved about 2.2% in this selected
12-root development suite; the two optimizations together did not beat lazy
alone. This is not playing-strength evidence, and no Desktop release changed.
Do not overwrite these sources or outputs to run another experiment.
