# Final import-warmup repair

`odin_release_candidate/` is copied from finalized `odin_compact_guard/` r4.
Only `core_nb.warmup()` changes. `change-manifest.json` records all12 source
hashes and verifies that the entire AST outside that function is identical.

The old warmup called the live root controller with a short deadline. On the
Windows laptop, compiling preparatory history helpers exhausted that allowance,
so the controller skipped `root_search_nb` but warmup still set ready true.
Both r2 and r4 exhibited this with original `NUMBA_READY=True` and zero compiled
root signatures. Subsequent diagnostic compilation took133s/78s, respectively.
That illustrates the defect; those Windows times are not native Linux timing.

The new warmup compiles a finite depth-one start position directly through the
exact live root argument dtypes, outside any move deadline. It explicitly warms
the history and move-hint helper call signatures used by the Python controller,
then invokes the expired monotonic-clock objmode branch and resets its scratch
counters. Readiness remains false until the native root signature exists and
the finite compilation search completes without an abort. The referee still
measures the entire actual import and enforces its90s allowance.

Three mocked no-JIT regressions pass:

```text
python -m unittest lab.odin.warmup_fix.test_warmup -v
```

They verify that arbitrary preparatory delay cannot skip the root, and that
missing native signatures or a broken clock path cannot report ready.
An independent agent reviewed the argument types, finite workload and AST
identity and found no required changes.

The release controller should run the existing exact-ZIP native gate. An
additional fresh-process signature gate is available:

```text
python lab/odin/warmup_fix/native_gate.py --source EXACT_EXTRACT --output gate.json
```

The controller supplies the native CPU/resource envelope. This gate requires
native readiness immediately after import, import below90s, legal bounded first
calls, and no new root/clock specialization after normal and cap-mate searches.
It does not replace the full referee/perft/strength gates.
