# Odin release opening corpus

Frozen 5 September 2026 before any Odin/control candidate games on these starts.
All paths below are relative to this directory. `audit.json` is PASS.

- `development.fen`: eight paired development starts, indices 0–7. These may
  be used for candidate selection and debugging; they are never final evidence.
- `holdout.fen`: 40 separate starts, indices 0–39, for the single declared
  80-game, 120 s + 500 ms primary match against minimal rules-corrected Storm.
- `manifest.json`: hashes, reference details, and the fixed 16-start original
  Storm guard subset: **0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 18, 19, 20**.
  Play both colours on this subset, with the same full clock, and report the
  32-game guard separately from the primary 80 games.
- Matching `.jsonl` files retain source PGN headers, every prefix move, source
  game index, first-eight-ply family, geometry and independent reference score.
- `independent-screen.jsonl` retains all 60 final screening attempts, including
  exclusions. `provenance-pre-screen.json` records sources and deterministic
  selection policy; `raw/` preserves downloaded public archives and PGNs.

Selection uses actual 16-, 18- or 20-ply prefixes from PGN Mentor's Ding, Giri,
So and Aronian collections. It excludes every first-eight-ply move prefix in
the 20,000-position fitted-evaluation corpus and every transposition of those
prefixes. It also excludes positions from every saved day-one/day-two and
Storm match PGN, the old synthetic starts and the fitting positions. There is
one selected start per first-eight-ply board key, and development and holdout
have no keys or positions in common. These are exact early-board families,
not a claim of disjoint ECO categories or unrelated chess knowledge.

The split is assigned by deterministic family hash before reference analysis.
All starts have at least four developed minor pieces, at least one castled
king, no check, and at most one pawn of material difference. Independent
Stockfish 19 screening uses 200,000 nodes per position, one thread, 32 MiB hash,
fresh hash/game state and Windows CPU4. Acceptance requires an exact completed
iteration score within ±70 cp for White; `reference.nodes` records the total
fixed-budget nodes, while `exact_score_nodes` records when that completed
iteration was obtained. Neither an Odin nor a Storm module was imported.

The final 40 starts contain 16 e4, 16 d4 and eight flank openings, with mean
6.05 developed minors. There are 21 starts with both kings castled on the same
side, three with opposite castling and 16 with one king castled; 19 have
blocked opposing central pawns. Their reference scores range from −35 to
+70 cp. All begin in the opening, so this set does not independently isolate
endgame conversion; retain the separately labelled ending diagnostics.

The eight development starts cover three e4, three d4 and two flank openings,
averaging 5.5 developed minors, with reference scores −45 to +53 cp. They
contain no already opposite-castled or locked-centre position, a limitation
to supplement with the existing development diagnostics.

`draft-v1/` is deliberately retained but must never be used for matches. Its
audit found ambiguous bound flags in aggregate UCI information and no opposite
castling coverage. The screen was corrected to read exact streaming iterations
and prioritise opposite-castled starts before any candidate games. No final
match result was used to make that correction.

Before the first final game, the release coordinator must separately freeze
the candidate/control ZIP hashes, pinned referee hashes, native runner/resource
configuration, lanes and statistical plan. The primary gate requires all 40
pairs, no candidate operational failures and a paired 95% score lower bound
strictly above 50%. The original-Storm guard requires a positive score (>50%).
Do not extend the same final sample after inspecting its result or pool the
guard/development games with the primary score. This opening manifest is an
input to that complete run declaration, not a substitute for it.

Reconstruction audit:

```powershell
& "$env:LOCALAPPDATA\ChessTK\venv312\Scripts\python.exe" `
  "lab/odin/release_openings/audit.py"
```

The reference executable and all PGN/position data are offline lab artifacts;
none belongs in the uploaded agent archive.
