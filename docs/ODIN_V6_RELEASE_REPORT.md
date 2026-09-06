# Odin v6 released — 6 September 2026

Historical release report. Desktop `agent.zip` was superseded by Tempest r1 on
6 September at 13:39 UTC; v6 remains preserved as `Odin-v6.zip`. See
`TEMPEST_R1_RELEASE.md`. The match evidence below is unchanged.

Desktop `agent.zip` now contains the exact tested Linux Odin v6 archive.
An identical `Odin-v6.zip` is on Desktop; `Odin-v5.zip` remains preserved.
No site upload was performed. The four Day 3 PGNs received before this
promotion correspond to the user's reported v5 upload, not this new release.

**SHA-256:** `cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647`.
Source: `odin_v6/`. Full artifact and evidence:
`lab/odin/native_release/odin-v6-architecture-r1/`.

## Completed overnight result

| Measure | Result |
|---|---|
| Opponent | Exact released Odin v5 |
| Games | 112, all 56 frozen color-reversed opening pairs |
| Wins / draws / losses | **30 / 69 / 13** |
| Points | **64.5/112 — 57.59%** |
| Paired 95% score interval | **52.23%–62.95%** |
| Match-relative Elo estimate | **+53**, interval approximately +16 to +92 |
| Operational failures | **0 for either engine** |
| Legal plies replayed | **14,743** |
| Frozen promotion criterion | PASS: paired lower bound strictly above 50% |

These estimates describe this paired match against v5 on the signer;
they do not predict leaderboard rank or guarantee a similar score against
stronger or stylistically different opponents. The 18 short screening games
are not pooled with this result.

Games completed by 04:53 UTC, 05:53 London. Terminations: 43 checkmates,
54 threefold repetitions, nine fifty-move draws, six insufficient-material
draws. No game reached the 600-ply cap. All frozen identities, clock recurrence,
fresh-agent services, resource envelopes and extracted-source checks passed.

V6 cold starts across all 112 games: median 34.078s, maximum 35.342s.
Its smallest observed remaining clock before increment was 398.672ms.
Median final clock was 6.856s, versus 5.855s for v5. Non-mate search-depth
medians were 17 versus 16; these are descriptive because the engines visited
different positions.

## What produced the gain

Original non-mutating legality and checking-move tests, pin shortcuts,
capture/promotion-only quiescence generation, first-blocker ray masks and
arithmetic-equivalent fused evaluation remove redundant work. Search settings
and evaluation weights remain v5's. The controlled 40-position benchmark
measured 1.5714x throughput with identical equal-node results. The overnight
match now provides separate evidence that this speed translates into strength.

The exact archive also passed native cold-start, perft, deadlines, official
protocol and current-referee/history checks before the match. Full correctness
evidence is documented in `ODIN_V6_MORNING_REVIEW.md` and the architecture
manifest. No neural experiment or third-party engine is included.

## Audit failure and repair

The automatic post-match report failed because its subprocess lacked the
pinned starter directory on `PYTHONPATH`: `ModuleNotFoundError: harness`.
Both game lanes completed successfully; their logs were intact. We reran the
**unchanged validator** with the correct pinned import path, first on Linux,
then independently on the downloaded logs locally. Both full audits passed.
No game was rerun, dropped, relabelled or selected after the result.

Original `audit.stderr`, `audit.stdout` and `COMPLETE.json` are retained.
Authoritative repaired reports are `overnight112/review-audit.json` and
`overnight112/local-review-audit.json`. The original missing
`final-audit.json` is not presented as successful. The future local controller
now preflights its audit imports before launching and explicitly passes the
pinned path to the final audit subprocess. Frozen match sources were not edited.

The Linux ZIP's 12 members were verified against the architecture manifest
before atomic Desktop promotion. `odin-v6-release.json` records hashes,
statistics, telemetry, authorization context and the release timestamp.

## Day 3 follow-up

Four supplied games, rounds 31–34: one win against xx; losses against ms,
AI Fellows and adashima, all by checkmate. V5 cold starts were 43.9–58.8s.
The detailed finite-reference review and v5/v6 critical-position diagnostics
are saved separately under `lab/odin/day3/`; they do not alter or contaminate
the completed overnight score. See `ODIN_DAY3_REVIEW.md` for findings.
