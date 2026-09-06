# Agamemnon: learning the backed-up search decision

Authorized 6 September 2026, following `docs/AGAMEMNON_FRONTIER_RESULTS.md`.
Work is isolated here. Tempest r1 remains the competition release.

1. Start from original turn-aware seed 260909 weights and the frozen 50% hybrid.
   Preserve score provenance through the existing selective search. Propagate
   the actual chosen child leaf and legal PV; reject untraceable TT/pruning/draw
   endpoints. Verify tracing on/off fixed-depth identity and replay each PV.
2. Obtain a bounded 64 MiB prefix of January 2025 rated standard Lichess PGNs
   under CC0. Retain one root per game and canonical position at ply 20, and
   deduplicate root transpositions/colour mirrors. Freeze 2,560 training,
   320 development and 320 sealed roots before teacher collection. No claim
   of disjointness from earlier anonymous public pretraining can be made.
3. Pilot 128 training + 32 development roots, then collect the remaining
   2,720 nonsealed roots. Own search: requested depth 5 with a 100k-node cap,
   fresh hash, full window per alternative; fall back to completed depth 4/3.
   This is our search policy at fixed depth, not competition iterative timing.
   Preserve the original game history, including for the offline teacher.
4. Label the own choice, teacher top alternatives, played move and deterministic
   random alternative. Teacher shortlist 64k nodes/MultiPV3, then independent
   forced-alternative 32k-node labels and refutations; latest complete unbounded
   iteration, no aggregated stale-bound flags. Teacher never enters an agent.
5. Fit only noncheck, capture/promotion-free traced endpoints. Remove cross-split
   exact/mirror leaf collisions and matching development leaves from replay.
   Conditional training regret compares retained alternatives, not all legal
   moves. It must never be represented as a playing-strength result.
6. Compare pair preference, static loss, half pair/half static and replay alone,
   using identical initialization, seeds, pair batches, replay draws, update
   counts, rate and checkpoint rule. Two seeds. Full replay guard MAE <235cp;
   select only if development conditional regret improves over epoch zero.
7. After the shallow objective comparison, test an original 16-unit residual
   nonlinear mover/opponent head. Zero output initialization exactly preserves
   the initial function. Verify gradients and colour/turn symmetry; retain
   original integer incremental embeddings. Compare pair/static objectives.
8. Freeze primary-seed candidates at 25% and 50% mixing, deduplicating unchanged
   functions. Repeat Tempest/mix controls on Linux; six perft cases, 5,288 exact
   accumulator checks and output parity, ABA state reset, cold init <80s.
   Screen the existing 110 development roots at 200k nodes and 300ms allowance.
   Nomination requires >=5cp improvement in capped equal-wall teacher regret,
   no extra >200cp errors, and no fixed-node regression. This gate is frozen
   before candidate training results are available.
9. Only nominees advance to paired games, followed by independent competition-
   clock confirmation and full release gates if the playing evidence supports
   it. No sealed evaluation or confirmation opening is consumed by training.

Operational limits: four local teacher/search lanes on distinct CPUs; each
teacher has one thread and 32 MB hash. Two Linux probe lanes at most, each
1800 MB/no swap and one pinned CPU. No new purchases, automation, deployment,
third-party engine port or published model. `zstandard` was installed in the
local research venv solely to read compressed data; it is not an agent dependency.

Pilot repair: the ancillary hybrid-base feature originally applied an extra
side sign to the handcrafted White score. Raw pilot records are preserved;
the preparation code corrects that feature by schema before fitting. Search
scores and legal traced PVs were unaffected. The corrected prepared features
must reproduce the quantized leaf values within 3cp. Expansion uses explicit
`white-v2` features. Pilot fits have only four eligible development groups and
are pipeline checks, not objective-selection evidence.
