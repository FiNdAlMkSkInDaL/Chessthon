# Tempest r1 — conservative referee and exact-endgame release

The tested Linux archive is not in git. Its SHA-256 is:

`0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4`

Odin v6 is preserved outside git, hash beginning `cd3ed778`.
No website upload was performed. Canonical source: `tempest_exact/`.
Archive/evidence: `lab/odin/native_release/tempest-exact-r1/`.
The separate `tempest/` directory remains the rules-only fallback.

## What changed

1. Native fifty-move terminal checks now use actual halfmove 100, preserving
   mate/stalemate precedence. This matches the [updated official referee at
   284724a](https://github.com/advitrocks9/aichessathon-starter/blob/284724ab56cecb2a1a9a4e5769b4748adab4ed90/harness/referee.py).
   Actual third repetition and the 600 absolute-ply draw cap remain the lab
   referee's other boundaries. The engine's historical search-cycle heuristic
   is explicitly separate from actual referee repetition.
2. Original, exhaustive **KQK and KRK mate-distance tables** provide exact
   three-piece conversion/defense. They take 257,222 compressed bytes and do
   not contain an external engine's answers. The original retrograde generator
   is `lab/tempest_build/generate_three_piece.py`. Shipped tablebases are
   expressly allowed by the [current competition rules](https://aichessathon.com/docs/rules.md).
3. The root policy chooses the quickest forced mate for the major-piece side,
   a draw/capture or longest defense for the bare king, respects the fifty-move
   and absolute-ply horizons, and avoids an immediately known third repetition.
   Mate on the boundary takes precedence. Existing history observation and
   legal UCI checks remain in place.

This does not replace the middlegame search, fitted evaluator or clock. The
neural and linear pilots are excluded. The main defensive weaknesses in the
ms, AI Fellows, adashima and new Neural Gambit games remain unresolved.

The data is exact for the three-piece graph. Full arbitrary historical
repetition is not encoded in the table: the root avoids an immediate known
third occurrence, but the table is not a history-expanded proof for every
possible inherited game history. Optimal mate-distance descent itself does
not cycle. Other material configurations continue through the existing engine.

## Validation completed

- **767,564 legal states and 9,360,880 forward legal edges** exhaustively checked
  against the independently tested native generator. Every table entry satisfies
  the mate/draw terminal or minimax-distance recurrence.
- Independent python-chess legal-move comparison on 4,000 sampled states.
- **640 complete conversions, 10,580 plies**, including both attacker colors,
  all at the stored mate distance. Explicit mate-at-halfmove-100 and
  mate-at-absolute-ply-600 fixtures pass. Unsupported material bypasses the policy.
- Local integrated native current-rule boundary checks and six perft positions.
- Linux one-core/2 GiB source-bound native gate **PASS**. Cold imports:
  **32.917s structural and 33.623s protocol**. Added three-piece protocol requests
  also passed the deadline/legal-output checks. Full extracted member identities
  match the tested source and original data.
- Current-rule Linux paired short smoke: **5 wins, 4 draws, 3 losses** against
  exact released v6, 100ms search allowance, six used opening pairs, **1,441 legal
  plies**, all replayed. Three candidate moves used the exact policy. Source/data
  hashes, worker resets and both color assignments passed audit.

- Two additional **full-clock games both drew**, one by fifty moves and one by
  repetition. All **246 legal plies** passed replay, clock and resource audit;
  **zero operational failures**. Four fresh processes used the exact archives,
  current referee and 120s + 0.5s control. Candidate cold imports were 33.885s
  and 32.934s; minimum request deadline headroom was 494.209ms. Evidence:
  `fullclock-pair.jsonl` and `fullclock-audit.json` in the native stage.
- Independent Linux regeneration produced identical queen/rook arrays and
  uncompressed NPY entries. The shipped table file remains unchanged.

These small match samples are **not reliable Elo estimates** and are not
pooled with each other or old v6–v5 games. The exact-state proof supports the
specific endgame improvement; it does not establish a general strength leap.
The two full-clock games completed after the archive was staged and before handoff.

In the round-35 queen-ending position before move 79, the table proves mate
within **11 plies** against optimal defense. A separate fixed-50k-node v6-based
diagnostic took 40 attacking moves against its finite reference defender from
that position. This illustrates conversion value; it is not an Elo comparison.

## Development failures retained

The first rules-only native-gate launch lacked the workspace `PYTHONPATH` and
failed before starting agents; corrected invocation passed. The first paired
short-smoke attempt failed the generic reset before games because it attempted
to write a read-only table array. The lab worker now verifies immutable arrays
instead of writing them; the production archive was unchanged. Both completed
lanes then passed A–B–A isolation. No failed game was removed or relabelled.

The neural scalar pilot failed on unseen opening families. The linear control
improved average error but failed phase/quiet-tail guards. Details, all trials,
the new-game analysis and next research priorities are in
`TEMPEST_IMPLEMENTATION_STATUS.md` and `lab/tempest_build/implementation-results.json`.
