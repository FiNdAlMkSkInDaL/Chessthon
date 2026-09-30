# Day 3 review — rounds 31–34, 6 September 2026

The four supplied games were played by the user's reported Odin v5 upload.
At receipt, the signer archive (not in git) was verified as v5 (`c7d8972e…e21102`). The
site exports do not embed an archive hash. **the signer archive (not in git) has since been
promoted to v6**, after its separate 112-game match passed; these Day 3 games
must not be attributed to v6.

| Round | Opponent | Our color | Result | Init | Final clock |
|---|---|---|---|---|---|
| 31 | xx | Black | Win, checkmate | 46.0s | 4.025s |
| 32 | ms | White | Loss, checkmate | 46.9s | 4.8s approximately |
| 33 | AI Fellows | Black | Loss, checkmate | 43.9s | 8.6s approximately |
| 34 | adashima | White | Loss, checkmate | 58.8s | 8.332s |

**1W / 0D / 3L.** All PGNs replay legally to their recorded checkmates.
There are no reported flags, crashes or initialization failures. Four games
against different opponents/openings do not estimate an engine's general
strength or justify comparing raw daily records across versions.

## What happened

**31, xx:** a long, approximately level endgame eventually broke when White
played **96.Nxe5?**, allowing **96...Kxe5** to win the knight. The 100k-node
reference changes from about +0.35 for White before that move to -7.99 after.
Odin converted and mated on move110. This win is evidence of conversion and
clock survival, not a demonstration that Odin strategically outplayed the
opponent throughout. An initial shallow screen flagged 48...Ne6; a deeper
same-root check reduced its estimated cost to only 0.08 pawn, so it is not
retained as an important error.

**32, ms:** positional deterioration starts well before time trouble.
At **12.Rae1**, with 107.6s available, the deeper reference prefers **12.Nb3**:
roughly +0.04 versus -0.68 from White's perspective. At **17.Qg4**, with
91.7s left, it prefers **17.Kh2**; the same-root estimates are -2.37 versus
-4.46. The position was already difficult before Qg4, but that choice made
it substantially worse. Treating the eventual mate as a clock failure would
miss the earlier decision errors.

**33, AI Fellows:** the clearer early error is **10...Be6**, with 107.5s left.
The deeper reference prefers **10...Bd7**, approximately -0.41 versus -1.93
for Black. The shallow suspicion about 9...a4 did not survive the deeper
check: its measured cost was effectively zero. **24...Bxe4**, with 70.1s
remaining, worsens an already losing position: about -4.30 for best defense
(24...Kh7), versus -6.03 for the capture. White's connected queenside passers
subsequently dominate. More depth alone did not correct the selected decisions
in the v6 probes below.

**34, adashima:** this is the strongest new diagnostic. The deeper reference
prefers **20.c5** to **20.exf5**, approximately -0.34 versus -2.14 for White.
Then **21.e7**, with **87.2 seconds still available**, compounds the damage:
**21.f6** scores about -1.99; the played advance scores -4.76. Our dangerous-
looking pawns do not compensate for Black's resources, including ...Qb8 and
the central counterplay. The site search reported only -0.34 after choosing
e7, so its assessment was much more optimistic than the independent deeper
reference. Different engines' centipawn scales are not directly calibrated,
but the move comparison and eventual continuation make this a useful case.

## What v6 changes in these positions

Eight selected roots were reconstructed from the full PGNs. Each version
received only historically available served-position/own-move history;
the old engine's transposition table was unavailable and was cleared.
Both versions ran on separate CPU-affined Linux lanes, once using the
recorded remaining clock and once at a fixed3s search allowance.

Both completed all16 probes with valid moves, native readiness, unchanged
source hashes and no additional compiled root signatures. **V5 and v6 chose
the same move on all eight recorded-clock probes.** V6 completed one extra
depth in five of them. It still chose 12.Rae1, 17.Qg4, 10...Be6, 24...Bxe4,
20.exf5 and 21.e7. The fixed3s test changed one choice (17.Be3 instead of Qg4),
but that isolated change is not established as an improvement.

This does not contradict the separate overnight result: v6 beat v5 with
57.59% points over112 games. It does show that the measured throughput gain
has not removed these specific decision weaknesses. Do not promise that
v6 would have won these same three site games.

## Next development priority

Use v6 as the released baseline. Investigate **search selectivity versus
evaluation error** on the six confirmed decision errors above, then broaden
to unrelated positions before choosing any change:

1. Compare the unchanged v6 search with diagnostic variants disabling late
   move reductions, futility/reverse-futility and SEE pruning, separately,
   at equal nodes and at equal time. Use a wider root comparison to expose
   the alternative lines. If a feature suppresses a good line, isolate the
   condition before changing it.
2. If wider search still prefers the problematic continuation, examine the
   evaluation along the contrasting lines: pawn support/blockade, promotion
   races, mobility and opponent counterplay. Do not apply a generic penalty
   to advanced pawns or hardcode these positions; their value depends on
   concrete continuations and move order.
3. Keep Day3 cases as known regression diagnostics. Select new variants on
   separate opening families and freeze a fresh holdout for promotion.
   The completed112-game set has now been inspected and is no longer fresh.

This is a targeted investigation, not a diagnosis that a particular pruning
rule or evaluation coefficient is already proven wrong. Increasing the
time budget is not the first change to make: these failures occurred with
substantial time, and v6's additional depth repeated them.

## Evidence and limits

`lab/odin/day3/reference/` contains all485 position analyses at100k nodes.
`deep-reference.jsonl` contains eight same-root unrestricted/played-move
comparisons at2M nodes per search. The reference is our offline Stockfish19
executable, single-threaded, hash cleared per search, full PGN history, last
completed exact iteration. It is a finite analysis, not game-theoretic truth.
No engine code or answers from this review enter the submission.

`v5-probes.jsonl`, `v6-probes.jsonl`, `selected-roots.json` and
`review-summary.json` bind inputs, source hashes, decisions and timings.
The signer differs from site hardware, and historical engine TT contents
cannot be reconstructed from PGNs. These are selected diagnostic positions,
not strength-test games. They are never pooled into the overnight result.

The first generalized screen launch hit a relative-path error before writing
metadata. Its empty outputs and error logs remain; corrected runs under
`reference/` completed all positions. No failed or missing analysis is
silently represented as complete.
