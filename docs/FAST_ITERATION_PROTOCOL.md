# Faster Odin iteration — implemented screening pipeline

Implemented on5 September in `lab/odin/fast/`. The actual worker imports the
unchanged source once, requires its native readiness and exact compiled root
signature, and runs the real `agent.get_move` entrypoint. Two documented,
in-memory driver substitutions replace the wall deadline with a fixed node
budget. Production source files and archives receive neither substitution.

Every game restores source-module arrays, lists, dictionaries, sets, scalars,
native TT/history/killers and the fallback TT. Each worker passes A–B–A
isolation before games start. Fresh baseline processes on different laptop
cores and Linux agree on move, score, depth and nodes. An additional four-game
Linux A/A control reproduces every paired move/depth/score/node count and
scores exactly50%. See `aa-audit.json`, `screen-report.json` and the raw logs.

The first screen completed96 games,48 per candidate, on24 fresh paired
openings. Four laptop lanes and two VPS lanes each ran one active mover/core.
Laptop lanes took at most721s including both cold imports; Linux lanes took
about110–125s. The experiments use20000 nodes/move, so these figures do NOT
describe full-clock throughput. Resets took0.03–0.11s, compared with33–34s
Linux cold imports and94–102s laptop cold imports. Laptop timings are offline
screening measurements, never evidence of compliance with the90s platform
limit. Every source independently needs an exact-source Linux gate.

Aspiration-only scored13W/15D/20L (42.71%). Adding selective pruning safeguards
scored19W/12D/17L (52.08%). The latter's narrow lead is exploratory, not a
confidence claim. A predeclared guards-only ablation removes the losing
aspiration component and uses the same development pairs; those repeated
pairs are not independent confirmation. See `guards-policy.json`.

The user explicitly requested112 overnight games for the next selected
candidate versus released Odin v5.56 separate opening families are frozen for
that run. `opening-audit.json` verifies all80 new families are distinct, excludes
the previous48 test families and checks against10398 known positions.
`freeze_v6_plan.py` binds archives, openings, clocks, referee, helper files and
package versions. `overnight_v6.py` launches two native lanes and automatically
audits complete results; it never promotes an archive. Read the separate
`ODIN_V6_OVERNIGHT.md` handoff for the selected source and live job identity.

The user explicitly prioritized rapid improvement cycles over the former
112-game release-confidence requirement. Odin R10 was released from16 fully
audited full-clock games plus its native correctness/runtime gates. It scored
9W/2D/5L against current-rules Storm. That practical decision does not establish
a precise win rate. Do not restore the112-game gate as mandatory by default.

The design below is retained as rationale. Explicit state restoration was
implemented on both operating systems; no fork-based worker was needed.

1. Separate correctness, runtime compatibility and playing strength. Run fast
   perft/state/targeted regression checks first. Keep a small number of fresh,
   cold, exact-source Linux protocol/clock checks for each release. A large
   self-play sample is not needed to recheck a source hash or import contract.
2. Screen candidate changes at short time controls across many independent
   openings, with both colors. Use laptop workers as well as the two VPS cores.
   Benchmark useful concurrency, RAM and per-core speed before choosing a
   worker count. Do not oversubscribe wall-clock matches, especially on
   heterogeneous laptop cores. Keep laptop and native-clock results separate.
3. Amortize compilation in the OFFLINE test harness. On Linux, import/JIT each
   candidate in a clean parent, then fork independent game children from that
   unchanged parent, preserving one-game state isolation through copy-on-write.
   Investigate fork safety with the actual single-thread Numba/LLVM runtime;
   do not assume it. On Windows, persistent workers need an explicit, audited
   reset of every Python/native history, TT, killer, counter, clock and cache.
   A history.reset call alone is insufficient. Prove A-B-A replay isolation
   before trusting that optimization. Production must still cold-import and
   cannot depend on a persistent JIT cache or warm parent.
4. Use fixed-node or short-clock comparisons as inexpensive screens, explicitly
   acknowledging that they do not test full-clock allocation or flag risk.
   Never let a candidate's partial warmup/readiness override masquerade as
   production behavior. Label any test instrumentation and bind all reports
   to source hashes, openings, node/clock limits and helper versions.
5. Predeclare sequential acceptance/rejection thresholds and an indifference
   region appropriate to a worthwhile gain before running a new experiment.
   Stop clear regressions promptly and send only promising changes to a small
   full-clock gate. A fixed practical budget with an honest inconclusive result
   is also valid. Do not repeatedly peek at an ordinary95% interval and call
   an eventual favorable crossing a calibrated sequential test.
6. Preserve the existing eight development openings and their history; use
   fresh independent opening families for new confirmation. Never tune on the
   final16-game results and then describe those games as an untouched holdout.
   The20 latest site diagnostic roots are now known development data.
7. Measure games/hour, initialization fraction, useful nodes and CPU/RAM
   utilization. Current Linux imports are approximately34s for Odin and30s for
   the control: roughly64s of avoidable startup per OFFLINE comparison game.
   This especially dominates short tests. More Linux cores are the direct
   multiplier for exact-clock throughput, subject to sufficient RAM; the
   existing two-core VPS cannot produce more CPU time by running more matches.

For the next engine changes, retain Team1 move29 (Kf2), FuzzyBot move43
(Rc4 versus Nf5), JSP move32 (Qd8 versus Bxd5), and near-drawn rook-versus-bishop
positions as targeted diagnostics. Odin already recovers Team1 move25 under
its recorded clock and NeuralGambit move26. Test general improvements; never
hard-code those answers into the submission. Details and full histories are
in `docs/ODIN_NEW_GAMES_REVIEW.md` and `lab/odin/new_games/`.

Reference for established distributed engine testing and sequential workflows:
https://github.com/official-stockfish/fishtest
