# Odin native release tools

These helpers use exact submitted ZIP bytes, fresh processes and read-only
extractions. They never build an agent, modify `harness/`, patch readiness or
upload to the site. `linux_match.py` was adapted from the proven historical
Storm runner; the historical file is unchanged.

The default harness is the independently pinned official starter at
`lab/odin/official-harness-91f70e54` (commit
`91f70e54be07e1bf56311962044a08b822c3af50`). All executable referee/rules/runner/
sandbox paths are selected before importing portable match helpers. Current
termination is `board.ply() >= 600`, resulting in a draw after standard terminal
outcomes take precedence.

## Before freezing a strength plan

Run the exact candidate and rules-corrected control through the native gate:

```sh
python -m lab.odin.release.native_gate \
  --validation-root "$PWD" \
  --harness-root "$PWD/lab/odin/official-harness-91f70e54" \
  --archive candidate.zip --cpu 0 --cold-target 60 --odin-rules \
  --output candidate-native-gate.json
```

Omit `--odin-rules` for original Storm, whose historical rules are intentionally
preserved. `--cold-target` is an explicit engineering margin, separate from the
official 90-second ceiling. The probe imports the original exact agent, requires
its unchanged `NUMBA_READY` and warmed root signature, then checks six standard
perft positions at depth three, twelve timed searches, legal choices, valid cap
and mate precedence, and repeated synthetic long-history bounds. It separately
runs a fresh exact archive through the unchanged official runner, with native
single-core/2-GiB envelopes in both processes. The synthetic histories test buffer
bounds; they do not purport to be complete legal played games.

## Freeze the plan

The complete schema is documented in `plan.py`. Use `source_provenance(root,
harness_root)` to generate the source map after tool edits finish. Every suite
declares the exact candidate and baseline SHA-256, complete opening-file SHA-256
and ordered FEN list, lanes with disjoint indices and CPUs, required pair count
and explicit decision criterion/threshold. `criterion: "paired_ci_lower"`
requires the lower 95% paired confidence bound above `threshold`;
`criterion: "raw_score"` requires the final full-sample score above it while
still reporting the paired interval. Both colours are generated for
every opening. To reproduce the prescribed tests, declare 40 pairs for `primary`
against the minimal rules-corrected Storm control and 16 pairs for `guard`
against original Storm. The prescribed primary criterion is
`"paired_ci_lower", threshold: 0.5`; the original-Storm guard criterion is
`"raw_score", threshold: 0.5`. The guard does not require its lower confidence
bound to exceed 50%. Neither corpus may be used for candidate tuning.

Changing any source bytes after declaring this plan requires a new plan before
starting the full test. The plan file is hashed into each run. Exact source and
package identities are checked before a planned run starts. ZIPs are privately
copied, audited and hashed again; an existing JSONL log is never appended.

## Run and audit

```sh
python -m lab.odin.release.linux_match \
  --validation-root "$PWD" \
  --harness-root "$PWD/lab/odin/official-harness-91f70e54" \
  --candidate candidate.zip --baseline rules-control.zip \
  --openings primary.fen --cpu 0 \
  --plan release-plan.json --suite primary --lane a --log primary-a.jsonl

python -m lab.odin.release.validate_match \
  --plan release-plan.json --suite primary --out primary-audit.json \
  primary-a.jsonl primary-b.jsonl
```

The validator requires complete predeclared lane coverage, colour pairing, exact
archive/plan/helper/referee/package identities, all 120000+500 clock records,
fresh agent-service IDs, resource samples, immutable extraction and verified
cleanup. It legally replays every PGN and every request FEN/UCI under current
claim-draw and total-ply semantics. It computes the existing paired-bootstrap
statistics with 20,000 resamples, seed 20260904 and 95% confidence. Evidence
validity and statistical promotion are reported separately. An operational
failure may stop a run after its colour pair; the resulting incomplete run
cannot pass. There is no outcome-based early stopping or selective rerun.

Native fidelity limits are recorded: signer CPU differs from competition CPU;
source permissions are read-only without a container mount namespace; private
temp lacks an aggregate 256-MiB filesystem quota; AF_UNIX-only socket creation
is enforced. Each agent gets one logical CPU, a full-core CPU quota, 2 GiB memory,
no swap, 128-task ceiling and single-thread library environment.

The service lifetime ceiling is 900 seconds, an outer cleanup watchdog separate
from competition move clocks. The first side remains alive during both cold
imports and both players' thinking: 180 seconds of permitted imports plus 240
seconds of initial banks plus up to 300 seconds of increments can total about
720 seconds in a legal 600-total-ply game. The historical 600-second watchdog
would incorrectly terminate some long games.

Lightweight evidence tests (no engine imports):

```sh
python -m unittest lab.odin.release.test_evidence -v
```
