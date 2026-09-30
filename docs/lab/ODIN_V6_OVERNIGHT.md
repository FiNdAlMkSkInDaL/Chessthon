# Odin next generation — live handoff

**Authoritative current status:** see [ODIN_V6_MORNING_REVIEW.md](ODIN_V6_MORNING_REVIEW.md).
Odin v6's architecture candidate is packed and natively gated; the new 112-game
overnight test launched at 23:30 UTC. The development history below is retained
for provenance and contains superseded pending/running statuses.

## Current steering and architecture work — 5 September, 23:24 UTC

The 192-game deeper confirmation finished: IIR disabled scored 52.083%,
SEE ordering 50%, IIR delayed 48.958%, combined SEE/IIR 48.958%.
The separate continuation-history candidate scored 47.22% in its 18-game
screen and was rejected. The user explicitly answered **keep searching for
a larger change**, so no overnight match was launched from these results.
The older "confirmation running" text below is historical.

An original 12-configuration piece-square neural experiment is recorded in
`lab/odin/fast/network-training/`. Every configuration generalized best at
the first epoch; further training overfit. Its best reused-validation MAE
was 96.81cp versus Odin's 97.25cp, insufficient to justify runtime integration.
No network is in any candidate or signer archive.

The active architectural direction removes work from the existing search
without changing its chess semantics:

- `odin_direct_legal/`: non-mutating legality tests, pin shortcuts and exact
  post-move occupancy for king/EP/castling cases; includes the proven fused eval.
- `odin_direct_noisy/`: additionally generate only captures and promotions
  for quiescence, preserving original ordering.
- `odin_ray_core/`: additionally replace square-walking slider attacks with
  computed geometry ray masks and first-blocker bit scans. These are not magic
  numbers, imported engine tables or runtime answer data.
- `odin_fast_checks/`: additionally non-mutating gives-check tests and direct
  first/second-blocker pin detection.

Linux 33-root, 100k-node whole-search comparisons passed exact moves, scores,
depths and node counts: direct legality throughput 1.2744x, direct noisy
1.2989x, ray core 1.4425x relative to released Odin v5. Local legality tests
passed 9,221 positions / 218,670 moves and six depth-four perft fixtures.
The fast-check version additionally matched every legal move's gives-check
flag against python-chess. Ray masks passed 1,119,744 exhaustive occupancies,
20,000 random full-board occupancies, and MSB singleton/two-bit checks.

The first larger mixed-position benchmark completed all position comparisons
but its reporting code failed because a new input variable shadowed the result
list. No usable aggregate timing report was saved. The harness is repaired
and now streams each result before aggregation. Do not claim those failed
runs as completed benchmark reports.

Active VPS services under `generation-v1`:
`chesstk-checks-mixed-r2` (CPU0, 1M-node mixed-position equivalence/throughput),
`chesstk-checks-clock` (CPU1, 18 games on nine development pairs, equal 100ms
search-time allowance). Both use a 100% CPU quota and 2GiB group memory limit.
The latter invokes the original unmodified wall-clock search driver after
deterministic A-B-A isolation tests; it is NOT the competition 120s+0.5s clock.
Its complete logs must pass `audit_clock_screen.py`.

Remaining: finish these development measurements, freeze a single selected
architecture on Linux, pass exact-ZIP native gate, then launch the already
authorized 112-game full-clock overnight match against released Odin v5.
Do not modify the signer archive (not in git) before final evidence is reviewed.

---

The user expanded tonight's scope on5 September: test an entire generation,
aim for a substantial gain over Odin v5, then freeze one winner for112 overnight
full-clock games. The final overnight run has NOT started as of22:42 UTC.
the signer archive (not in git) remains released Odin v5, SHA-256
`c7d8972e823eb821c016010445d4b02996daff954d870d63083c445850e21102`.

The new warm-worker pipeline is implemented and validated; details are in
`FAST_ITERATION_PROTOCOL.md`. The initial48-game experiments scored42.71%
for aspiration-only and52.08% for aspiration plus selective safeguards. Removing
aspiration produced52.08% too. These small gains did not satisfy the user's
ambition, so none was promoted or put into the overnight holdout.

`lab/odin/fast/generation-policy.json` freezes14 original source variants under
`odin_generation/`. Each plays18 fixed20000-node games,9 color-reversed
opening pairs. Twelve variants run in two VPS generation lanes; SEE ordering
and mobility run in two laptop lanes. A baseline process is reused within each
lane with full per-game state restoration. The hardened worker rejects silent
native fallback and records forced moves as zero search nodes.

All14 candidates completed their18-game screens:252 games were replay-audited.
The screen leaders were SEE capture ordering (10W/6D/2L,72.22%), delayed internal
iterative reduction (9W/4D/5L,61.11%), and disabled internal iterative reduction
(8W/5D/5L,58.33%). This is population selection, not confidence evidence.
`generation-report.json` contains all14 results and source-bound log identities.

`finalist-policy.json` now freezes those top3 plus the compatible combination
`combined_see_order_iir_late` before any confirmation play. They each play48
games at100000 nodes/move on24 fresh paired openings. Active services are
`chesstk-confirmation-a` and `chesstk-confirmation-b`, in `generation-v1` on the
VPS. Each lane compiles the v5 baseline once and tests two candidates serially.
After both finish, run `generation_report.py` with `--policy` pointing to the
finalist policy, `--results` to confirmation-results, `--openings` to
generation-openings/confirm.fen, `--complete`, and a distinct `--output`.
The winner must score above50% and pass its exact-source native gate.

An orthogonal `odin_fused/` experiment fuses the existing fitted evaluation into
direct weighted accumulators. It passed937-position score equivalence and
33-position whole-search equivalence (moves/scores/depths/nodes), plus a native
Linux gate. Whole-search throughput improved23.36% on the laptop but only2.57%
on the Linux signer; do not represent the laptop number as a competition gain.
`fused-search-benchmark-linux.json` preserves the native measurements.

`odin_see_fast/` additionally skips a sign-only SEE calculation for obviously
non-losing captures. It retains SEE for all back-rank destinations to account
for promoting recaptures. `see-bound-test.json` checked12980 captures across
5867 positions, including3522 skipped calls and867 retained back-rank cases.
Whole-search equivalence/throughput and explicit promotion-recapture regression
tests are running locally. Do not apply it before those pass. If a SEE-ordering
finalist wins, the final optimized source must repeat native equivalence and
runtime gates before the overnight archive is frozen.

The112-game opening set is already independently frozen:
`lab/odin/fast/overnight-openings/openings.fen`, SHA-256
`a2a8f62cadf481adacbb101f87c34a6e7c7125569f49d1bfe672e2bbfe6fea67`.
It contains56 paired starts, separate from all development/confirmation
families. `freeze_v6_plan.py` binds the actual selected archive and exact v5
baseline. `overnight_v6.py` runs two persistent user-systemd lanes, audits their
complete results and never promotes an archive automatically.

VPS task directories live beneath the established signer base
`$HOME/chess-sign-odin-20260905`; no login material belongs in the repo.
`generation-v1` contains the population source and results. The initial
`chesstk-generation-a` and `chesstk-generation-b` have completed. All official
harness files remain unchanged.

The superseded R10 full112 plan remains cancelled with its stop marker. Do not
resume it or its old promotion watcher. Its16 completed full-clock games were
the user's practical release evidence for Odin v5, not a112-game result.
