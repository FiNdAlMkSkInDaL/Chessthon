# Odin preparation: expert review of Storm versus v3

Final cross-review: `ODIN_REVIEW.md` adds the completed tablebase and controlled
Storm probes for move 83 of opening 165. The tablebase confirms `Rg3` draws
and `Rf4` loses; the filter excludes `Rg3`, but retains four other drawing
moves. No claim is made that filtering alone forced the loss. The attempted
restricted reference label for move 61's `Kg8` is invalid and excluded.

Reviewed 5 September 2026. This report replays all 40 frozen native full-clock
games, reviews every loss and draw, and examines representative wins and long
conversions. It also distinguishes the eight short-screen games and four
historical-site-opening stress games. The ten new platform games are reviewed
separately by the Odin preparation session.

## What this evidence establishes

Storm scored **31 wins, four draws and five losses**, all 5,028 plies legally
replayable. Every logged FEN and UCI agrees with its PGN, and every terminal
result agrees with `python-chess` automatic claim semantics. The existing final
native audit separately establishes the frozen archives, one-core envelopes,
clock and source provenance. Storm made 2,520 decisions. All 36 decisive games
ended in checkmate; there were no operational losses.

The important weakness is narrower than the five-loss count suggests. **Only
one loss, opening 165 with Storm Black, ever had a positive completed Storm
search score.** The other four start and remain negative in Storm's own search:
opening 166 begins with a hanging knight, opening 167 with a hanging bishop,
opening 168 has an extra black pawn, and opening 177 starts with White's king
already on d4. These are unsuitable examples from which to claim that Storm
throws away equal positions. The paired reverse colours are retained and remain
part of the legitimate 40-game result.

Scores in this report are **Storm's own estimates**, not independent engine
ground truth. A declining score can reflect the opponent's reply, a change in
search depth, transposition-table contents or root filtering. It does not locate
the first blunder. Exact alternative moves require independent reference
analysis with the real prior history.

All five losses finish with **2.799–4.752 seconds**, mean **3.968 seconds**, and
Storm spends 62.983–74.611 seconds on their first 20 decisions. The thesis that
these losses were caused by leaving a large unused time bank is unsupported.
Most of their difficult endings were played from a small bank plus increment.

| Outcome | Games | Mean remaining seconds | Mean first-20 seconds | Mean played plies |
|---|---:|---:|---:|---:|
| Win | 31 | 15.345 | 64.525 | 125.6 |
| Draw | 4 | 33.699 | 55.743 | 93.3 |
| Loss | 5 | 3.968 | 69.254 | 152.2 |

The draw first-20 mean includes one game with only 12 Storm decisions; it is a
descriptive total of the available first 20, not a matched opening-time sample.
The final reserves include increment, and are reconstructed from the incoming
integer clock and complete referee-facing call duration.

## Highest-priority source-supported defect to investigate

In opening 165, before **83...Rf4**, the readable root PeSTO evaluation is
**+88 cp**. `agent.py` classifies that as winning because `history.WIN_CP` is
only 80. The root filter then rejects **83...Rg3** solely because its resulting
position has already occurred once. The latest completed searches had scored
zero. The eventual search over the permitted roots returns **-125 cp** for
`Rf4`.

Position before `83...Rf4`:

```text
2k5/4K3/6P1/8/4p3/5r1p/R7/8 b - - 5 83
```

This is not merely a speculative feature request. A source-only replay of the
actual `history.py` root-filter functions, with the observed sequence of served
and post-own-move position keys, removes `Rg3` and retains 12 alternatives,
including `Rf4`. The intended second-occurrence rejection occurs before the
deadline-sensitive deeper scan, so that rule itself does not depend on timing.
The replay disables the scan deadline; the complete set of other rejected moves
can differ from the original 50ms scan. It imports no engine and triggers no JIT.

The same filter excludes `60...Kg8`, `61...Kg7`, `65...Kc7`, `70...Kc6`,
`70...Kb6` and `72...Kb7` in this ending. At move 61, only `Ke7` remains out of
the two legal moves and the entrypoint returns it without search. At move 72,
static PeSTO remains +260 while the completed search for the played pawn break
is only +56. The filter is deciding which continuations are permissible from a
cheap evaluation that is already diverging from the search.

**Build instruction:** in the next candidate, replace unconditional
static-evaluation-based deletion of repeated roots with referee-aware terminal
draw valuation inside the root/search decision. A nonterminal second occurrence
must remain searchable. If all non-drawing continuations lose, retain the
drawing continuation. Apply preference for avoiding an available draw only when
the completed search establishes a better non-drawing alternative, with mate
precedence intact. Carry actual repetition history into this decision; a fresh
FEN alone cannot reproduce the problem. Do not simply raise the 80cp threshold.

**Acceptance gate:** independently label `Rg3` versus `Rf4` with full history;
test the same position under different repetition histories; test immediate and
claim-by-intended-move draws, a losing static-positive position with a saving
draw, and an actual winning alternative. Test the high halfmove-clock policy
separately. The recorded 40-game holdout contains **no Storm root with a halfmove
clock of 90 or greater**. Retain the old engine as the baseline and require
playing-strength evidence before promotion. No claim that `Rg3` objectively
saves this particular game is made by this descriptive report alone.

## Five losses

### Opening 165, lane a game 12, Storm Black

This is the clearest improvement case. Storm develops normally, castles on move
11 and gradually reaches a favourable self-evaluation. After
`48...Qxe5+ 49.dxe5 Rxa4`, it has rook plus four pawns versus rook plus three.
The a-pawn advances with `51...a4 54...a3 55...a2`, but its own rook on a1 blocks
promotion and White retains active rook checks. Black's king walks from g8 to
c4 and then back toward b8 while its score stays near +256 for moves 56–68.

`72...g5+ 73.hxg5 h4 74.e6 fxe6 75.g6 e5+` changes the position into a race of
widely separated passed pawns. White's king becomes active. After
`79...Rf1 80.Rxa2 Rxf3+`, Black has e4/h3 against g6 with one rook each. The
root-filter issue above arises on move 83. Later,
`88...Rxg7 89.Ra7+ Kd6 90.Rxg7` loses Black's rook to a skewer. The two remaining
pawns do not promote. The game ends with `108.Rh8#`.

| Black decision | Own score | Depth | Clock before, s | Complete call, s |
|---|---:|---:|---:|---:|
| 49...Rxa4 | +200 | 20 | 25.168 | 1.183 |
| 52...Kg8 | +247 | 20 | 19.816 | 7.143 |
| 55...a2 | +210 | 17 | 12.374 | 1.628 |
| 66...Kc4 | +256 | 20 | 7.399 | 0.832 |
| 69...Kb7 | +164 | 15 | 6.321 | 0.568 |
| 72...g5+ | +56 | 15 | 5.172 | 0.388 |
| 83...Rf4 | -125 | 16 | 4.110 | 1.174 |
| 86...Rg4 | -469 | 18 | 2.737 | 0.577 |
| 88...Rxg7 | -224 | 14 | 2.851 | 0.641 |
| 89...Kd6 | -500 | 18 | 2.710 | 0.876 |

Useful exact additional roots:

```text
Before 52...Kg8: 8/2R2p1k/6pp/4P3/p7/5P1P/7K/r7 b - - 1 52
Before 55...a2: R7/5pk1/6pp/4P3/8/p4PKP/8/r7 b - - 1 55
Before 68...Kc6: 8/5p2/6p1/3kP2p/R4K1P/5P2/p7/r7 b - - 19 68
Before 72...g5+: 1k6/5p2/6p1/R3P2p/5K1P/5P2/p7/r7 b - - 27 72
Before 88...Rxg7: R7/2k3P1/8/5K2/4p1r1/7p/8/8 b - - 8 88
```

These support targeted evaluation of blocked passers, rook activity behind and
in front of passers, king access, promotion distance and multiple-wing pawn
races. They do not prove which term or pruning decision caused the loss. The
published PeSTO-only evaluator lacks these relational features; the retained
untuned r3 evaluator is not a validated cure.

### Opening 166, lane a game 14, Storm Black

The initial position gives White `6.dxc5`, taking a knight; after
`6...dxc5`, Black is a minor piece down for a pawn. Storm's first score is
-256 and its best recorded score is -233. This game is principally defensive
play from an initially compromised position. By `23.Qxg4 hxg4`, queens are off
and White remains up a minor piece. Storm obtains counterplay with advanced
queenside pawns, but `42.Rxb4 cxb2 43.Rxb2` removes them. White's c-pawn reaches
c7 and `55.Rb8 Rxc7 56.Nxc7` leaves Storm without the rook. `66.Rh7#` ends it.

No positive-score conversion was thrown away. Preserve this as an adverse-start
defence test, not an evaluation-tuning target that demands a win. Its reverse
colour game is a Storm win, which is why this opening pair contributes one
point of two rather than evidence of a systematic Storm deficit.

### Opening 167, lane a game 16, Storm Black

White begins with `5.Qxe6`, taking the exposed bishop. After
`5...Qd7 6.Qxd7+ Nxd7`, the queens disappear and Storm is four material points
behind. Its initial completed score is -427 and its peak is -422. White
consolidates, collects pawns and promotes on d8. `69.Qe6#` finishes a game that
never had a favourable Storm score.

Again, this is not evidence of a lost winning endgame. The reverse colour leg
is a Storm win. The opening selection procedure used small initial static
evaluation, which did not detect such immediately available tactical material.
For Odin matches, screen opening starts with an independent deeper reference
and reject obvious hanging-piece imbalances before assigning the unseen test
split. Freeze that decision before running either candidate.

### Opening 168, lane a game 17, Storm White

White starts a pawn behind with its king on d2. `7.exf5 Bxf5` exchanges pawns;
Storm remains a pawn down. Its best recorded score is only -69 at `18.Rf1`.
The sequence `19...Nh2 20.Nxh2 Bxg5 21.Nf3 Bxh6` removes the advanced h-pawn;
after subsequent exchanges it reaches a rook ending with fewer pawns.

The critical descriptive phase is a race in which Black's h-pawn pins White's
rook to h1 while a central d-pawn advances. After
`49.Rxc6 Rh7 50.Ke3 h3 51.Rc1 h2 52.Rh1 d4+ 53.Kf3 d3`, White tries the
queenside pawn race with `54.b5`. Both sides eventually promote, but Black's
queen gives forcing checks while the h2 pawn and rook restrict White's king.
`67...Qg4#` ends a position with equal crude material: queen, rook and pawn per
side. Equality of P/N/B/R/Q points is plainly not king safety or equality of
position.

```text
Before 49.Rxc6: 2R5/p4r2/2p5/P2pk1p1/1P5p/8/3K4/8 w - - 0 49
Before 50.Ke3: 8/p6r/2R5/P2pk1p1/1P5p/8/3K4/8 w - - 1 50
Before 54.b5: 8/p6r/8/P3k1p1/1P6/3p1K2/7p/7R w - - 0 54
```

`50.Ke3` receives -380 at depth 16 from 13.938 seconds; `54.b5` receives -468
at depth 15 after a 3.082-second call from 6.892 seconds. This supports a
passed-pawn/race/king-safety diagnostic family, but not an assertion that these
particular moves lose a drawable position.

### Opening 177, lane b game 15, Storm White

White starts with its king on d4 and loses f2 after
`6.Kc3 Qh4 7.Be3 Nf6 8.d4 Ng4 9.Nf3 Nxf2`. The queens are exchanged, but king
exposure continues: `13.bxa5 Rxa5 14.Nc3 d5 15.Nxe4 Rb5+ 16.Kc3 Bb4+
17.Kd3 dxe4+`. Storm's scores go from -115 initially to -309 at move 17. The
game stabilizes for a while near -220 but White is still two pawns down.

Black then centralizes its king, activates both rooks and creates passers.
Storm is four pawns behind by move 57. After `75...Rc2+ 76.Kh1 Nxh3`, the
minor piece also falls. Black promotes on c1 and later f1 before `97...Rd8#`.
The root at move 6 is an exposed-king defence test; it is not representative of
a normal developed curated opening. Its reverse colour leg is a Storm win.

```text
Before 6.Kc3: rn1qkbnr/ppp2ppp/2bp4/4p3/1P1K4/3P4/P1P1PPPP/RNBQ1BNR w kq - 0 6
Before 15.Nxe4: 1n2kb1r/1pp2ppp/2b5/r2pp3/3Pn3/1KN1B3/P1P1P1PP/R3NB1R w k - 0 15
```

## Four draws

- **Opening 160, a-02, Storm Black:** Queen checks repeat after the rooks are
  exchanged. Storm's score is never positive and is zero for its final ten
  decisions. Final material is equal, with queen and two pawns each. This is
  successful defensive resource retention, not a demonstrated gifted win.
- **Opening 165, a-11, Storm White:** Only 24 played plies. After the queen
  exchange, `14.Ra3 Na6 15.Ra4 Nc5 16.Ra3 Na6 17.Ra5 Nc5` triggers the
  automatic claim mechanism before White is asked again. White's score is never
  positive; its final six searches score zero. The spare 92.303 seconds come
  from the early repetition. Keep this as a claim-by-intended-move regression,
  not as justification for automatic contempt in every balanced position.
- **Opening 169, a-20, Storm Black:** A modest peak score of +103 declines
  while White takes a3. After `44...Bxf4+ 45.Nxf4 Nxf4`, Black obtains checks
  with the knight and queen. `46...Nd5+ 47.Kg1 Qb1+ 48.Kh2 Qb8+ 49.Kg1 Qb1+
  50.Kh2` ends by repetition. The attack yields a draw, with no established
  missed win.
- **Opening 176, b-14, Storm Black:** The score peaks at only +19. Black later
  faces rook, bishop and pawns against its rook and pawns. The active king and
  a-pawn supply defensive resources. `72.e4 Rxe4 73.Bh8 Rxe1+ 74.Kxe1 f4
  75.gxf4 Kxf4` liquidates the rooks. The last pawn promotes with
  `80...a1=Q 81.Bxa1`, leaving bishop against bare king: insufficient material.
  This is a useful draw-preservation example. Penalizing all promotions that
  are immediately captured would incorrectly reject such a drawing liquidation.

## Strengths Odin must preserve

Storm wins 14 games in which its first completed score is negative. Twenty-five
of its 31 wins include a Storm promotion. The tactical wins are not all endgame
grinds; opening 174, Storm Black, finishes after 41 played plies, and opening
175, Storm White, after 51.

- **Opening 174, b-10:** `15...Qh4 16.Bb5+ Kf7 17.Bc3 Nf3+ 18.gxf3 exf3`
  opens lines against White's king. Storm's score rises from +98 at `16...Kf7`
  to +1074 at `17...Nf3+`, then finds a mate score at `19...Bxh3`. This is a
  concrete tactical-sacrifice preservation case for any evaluation or selective
  search change. Position before the played knight sacrifice:
  `r6r/pp3kb1/3p2p1/1BpPnb1p/4p2q/1NB1P2P/PPQ2PP1/R4RK1 b - - 4 17`.
- **Opening 175, b-11:** Storm castles queenside, uses `16.e5` and the h-pawn,
  then `21.hxg6 fxg6 22.Nf6` while answering checking attacks on its own king.
  `31.Rxg8#` completes the attack. A simple blanket aversion to exposed kings
  or sacrifice moves would damage a demonstrated strength.
- **Opening 160, a-01:** `29.Ra8 Qd8 30.Qa5 Qxa5 31.R1xa5` and the subsequent
  knight exchanges show that the engine searches through material temporarily
  disappearing during a sequence. The final endgame converts. Position before
  `30.Qa5`: `R1rqb1k1/4r1p1/2P1p1n1/1B1p1pNp/3P3P/2Q1P3/5PP1/R5K1 w - - 3 30`.

There are also slow wins worth improving rather than discarding. Opening 172
White takes 228 plies; opening 178 White and Black take 277 and 258. In the
277-ply win, Storm promotes on move 90 but does not reach a self-evaluation of
+500 until move 127; an opposing h-pawn on h2 and active rook complicate the
conversion. That is a queen-versus-rook/passed-pawn calculation problem, not a
bare-king mating problem. Preserve these complete games as long-horizon tests.

## Clock diagnosis and the changed live cap

The clock manager already varies effort. There are 64 recorded searches whose
complete call lasts more than three times the final logged soft target. This is
allowed: hard allowance is derived from the initial target, while the final
target can shrink with stable iterations. The log does not retain completed
iteration costs, attempted final depth, abort reason, root move scores or
root subtree effort. Consequently, the existing data cannot distinguish useful
extra search from a last-iteration attempt that produced no new answer.

**Build instruction:** add optional bounded diagnostic telemetry for initial
soft/hard allowance, filtered root count and reason, each completed iteration's
cost and score, last attempted depth/abort, and nodes spent on the top root
alternatives. The `SearchClock.root_effort` input exists but must be wired from
real measurements before using it. First compare complete-search result gain
per clock spent; then test a clock change as a separate candidate. Retain the
hard monotonic deadline. Do not spend toward an empty final clock as an objective.

The live contract fetched by the parent review on 5 September now uses a
**600-ply cap including the opening, scored as a draw**, superseding Storm's
historical 300-played-ply material regime. The saved live documents are
`lab/odin/live-agent-contract.md` and `lab/odin/live-rules.md`. This is a mandatory
successor protocol/referee update, independent of the chess conclusions here.

None of the 40 native holdout games reaches the old root switch at own game
ply 284: the longest game is 277 plies. Their results are not decided by the
old cap or material-mode root evaluation. This does not establish fidelity to
the new cap in a new match; new validation must use the updated official harness.

The separate **293-ply site-opening stress draw does cross that old switch**.
Black moves first, so Storm White's first old-material-mode call is `150.Kf5`,
global played ply 286 and telemetry p284. Its four affected requests are:

| Move | Telemetry p | Score | Depth | Search ms |
|---|---:|---:|---:|---:|
| 150.Kf5 | 284 | +300 | 5 | 250 |
| 151.Bf6 | 286 | 0 | 8 | 916 |
| 152.Rg5 | 288 | 0 | 7 | 408 |
| 153.Bd4 | 290 | 0 | 8 | 645 |

The preceding `149.Be5` has score +349, depth 8 and search time 2,222ms. The
position before `150.Kf5` is
`7r/6R1/8/4B2k/4K3/8/8/8 w - - 91 150`. The game ends after `153...Rh8` by
the fifty-move automatic claim at halfmove 99, not by the old cap. Bishop and
rook versus rook is not generally won. Neither the +349 estimate nor the final
extra bishop proves that the draw was avoidable. Do not label this entire stress
game as if it used the new rules or an unchanged evaluation throughout.

## The separate screens

The eight-game native 10s+100ms screen was +8=0-0 against v3. It preceded the
fixed holdout and is not additional full-clock evidence or part of the holdout
confidence interval. The four Windows full-clock site-opening stress games
were +1=3-0: Two Knights draw/win, King's Indian draw/draw. They are a small,
previously observed opening sample, not a fresh holdout or a native speed test.
The rook-and-bishop draw is described above. Another draw allows perpetual
queen checks despite extra pawns. Together these support better realistic
opening tests and conversion diagnostics, not a promised leaderboard Elo gain.

## Concrete implementation order for Odin

1. Update the cap/draw semantics and opening-age accounting to the newly fetched
   official harness. Preserve exact mate/threefold/fifty precedence. Remove
   obsolete late material evaluation and stale 300-ply time-horizon assumptions.
2. Repair the root draw-choice architecture described above. Keep the recorded
   full-history 165 positions as required regressions, independently labelled
   before making best-move assertions. Add save-the-draw and preserve-the-win
   cases; do not train on a blanket preference to avoid repetition.
3. Build a focused, inexpensive endgame evaluation candidate. First add tested
   passer masks, blocker/escort/king-distance features and rook activity relative
   to passers. Retain pawn-race counterexamples and tactical king-safety cases.
   Tune on a development split and benchmark native node-time cost; do not copy
   the broad untuned r3 weights and call that progress. NN evaluation is a
   separate later experiment if the rules, source form, warmup and native speed
   permit it, not a prerequisite for this repair.
4. Add bounded root and iteration instrumentation, then separately test improved
   allocation using real root effort and result uncertainty. Retain hard-deadline
   and forced-move behavior. A slower evaluator must earn its added node cost in
   full-clock strength, not only static loss or nominal depth.
5. Replace the synthetic opening generator as the primary strength corpus with
   realistic, developed and independently screened starts. Split by source
   game/opening family, not neighbouring FENs, and keep the test split unseen.
   Preserve these 40 games and the new platform games as development evidence;
   they are no longer fresh evaluation material. Play paired colours versus
   exact frozen Storm, using the current official referee. Freeze candidate and
   stopping criterion before inspecting results. Report game-level uncertainty
   and operational failures separately. Retain sacrifice regressions from the
   wins while fixing the endings.

This order is based on observed failure modes and source mechanics. It is not
a guarantee of first place, and it does not identify private opponent methods.

## Reproducible evidence

Run with the project's Python 3.12 environment:

```powershell
& 'C:/Users/finla/AppData/Local/ChessTK/venv312/Scripts/python.exe' -m lab.odin.holdout_review
```

`lab/odin/holdout_review.py` writes `lab/odin/holdout_review.json`, including
every ply's FEN, SAN/UCI, material, clock, own search telemetry, static root
evaluation and cheap root-filter rejections. It also replays the complete
source filter at six selected roots in the 165 loss. It does not import any
submission engine module or change any release, harness or engine file.

Input SHA-256:

- `holdout-r2-lane-a.jsonl`: `70dc3565814b4315516c2f3f53bb7e98f01259dd719eed4375c8c9671163b135`.
- `holdout-r2-lane-b.jsonl`: `700d6cf94fa51dd26d5821ccc8bf6f5c5cccfaefc10b378f834877b5545aa5b1`.

The fixed native score and paired bootstrap interval remain those in
`lab/storm/holdout-r2-audit.json`: 33/40 points, 82.5%, paired percentile
95% interval 71.25–92.5%. Never pool the short screen or Windows stress games
into that interval.

## Complete forty-game ledger

W/D/L and scores below are from Storm's perspective. IDs identify the lane and
game number in the immutable source logs. Clock is Storm's final reserve.

| Opening | Storm White: ID, result | First score | Clock, s | Storm Black: ID, result | First score | Clock, s |
|---|---|---:|---:|---|---:|---:|
| 160 | a-01, win | +54 | 9.441 | a-02, draw | -50 | 15.989 |
| 161 | a-03, win | +64 | 13.483 | a-04, win | -79 | 15.554 |
| 162 | a-05, win | -16 | 63.519 | a-06, win | +17 | 3.639 |
| 163 | a-07, win | -32 | 9.065 | a-08, win | +32 | 10.294 |
| 164 | a-09, win | +63 | 8.999 | a-10, win | -55 | 5.306 |
| 165 | a-11, draw | -2 | 92.303 | a-12, loss | +2 | 4.232 |
| 166 | a-13, win | +255 | 18.435 | a-14, loss | -256 | 2.799 |
| 167 | a-15, win | +420 | 4.363 | a-16, loss | -427 | 4.752 |
| 168 | a-17, loss | -117 | 4.083 | a-18, win | +117 | 8.807 |
| 169 | a-19, win | -57 | 6.481 | a-20, draw | +61 | 22.803 |
| 170 | b-01, win | +68 | 4.325 | b-02, win | -58 | 13.846 |
| 171 | b-03, win | -46 | 10.846 | b-04, win | +40 | 17.486 |
| 172 | b-05, win | -68 | 12.365 | b-06, win | +83 | 42.429 |
| 173 | b-07, win | +12 | 6.314 | b-08, win | -9 | 4.664 |
| 174 | b-09, win | +36 | 8.752 | b-10, win | -38 | 75.983 |
| 175 | b-11, win | +95 | 54.814 | b-12, win | -94 | 5.876 |
| 176 | b-13, win | -9 | 3.589 | b-14, draw | +18 | 3.700 |
| 177 | b-15, loss | -115 | 3.974 | b-16, win | +138 | 4.475 |
| 178 | b-17, win | +28 | 5.590 | b-18, win | -28 | 8.076 |
| 179 | b-19, win | +5 | 4.523 | b-20, win | -9 | 14.369 |
