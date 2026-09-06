# Storm's first ten platform games: evidence for Odin

Final cross-review: `ODIN_REVIEW.md` supplies the later 5-million-node streamed
reference confirmations, which supersede exploratory numerical comparisons
below where they differ. Full build instructions are in `ODIN_BUILD_BRIEF.md`.

Reviewed 5 September 2026. Sources are every PGN and companion log in
`chess_results_day2/`, rated rounds 16–25. The supplied logs identify our team
as **Finlay Phillips**. The user identifies this submitted release as Storm;
the logs contain the expected `S4` telemetry, but do not contain an archive
hash that would independently prove the uploaded bytes.

## Finding

Storm scored **6 wins, 1 draw, 3 losses: 65% of available points**. All nine
decisive games ended in legal checkmate. The draw was a correct prospective
threefold claim. The three losses show a stronger case for improving
positional evaluation and recognition of king attacks than for globally
spending more clock. They are three different failures to investigate:

- R17: a space/file disadvantage, a dangerous d-pawn, then a queen-and-bishop
  ending in which the opponent broke through.
- R18: restricted coordination and a damaged kingside pawn structure at
  equal material, then loss of the d4 pawn and a decisive advanced passer.
- R23: an accumulating king attack remained approximately equal in Storm's
  own search scores until the attacking pieces were already close enough
  to force major material loss. This is the clearest diagnostic priority.

The game descriptions below separate forensic observations from a later
independent reference layer. That layer gives concrete candidate repairs;
finite-budget reference analysis is still not mathematical ground truth.
A falling
`S4 s` value describes Storm changing its mind between its own turns; it
cannot by itself assign a blunder to the preceding move.

## Audit and timing

`lab/odin/site_review.py` legally replays all **1,143 plies / 572 Storm
moves**, checks every pre-move position has no already claimable outcome,
and reproduces every final result. It parses all **558 S4 records** and
matches them to the PGN roots. The other **14 moves were forced replies**;
together those took **0.030 seconds**. No PGN contains independent evaluation
annotations. No engine was imported to produce this audit.

`lab/odin/site_review.json` contains source hashes, every before/after FEN,
SAN/UCI, legal move count, material/passed-pawn descriptors, exact PGN clocks,
mapped telemetry and 44 selected diagnostic roots. Game ply is one-based
from the supplied starting FEN. `S4 p0` means our first served position; in
games where the opponent moves first, this is the second played ply, not
the first. Do not align `p` with PGN ply without this offset.

| Round | Opponent | Storm | Result | Played plies | Clock left | First 20 decisions |
|---|---|---|---|---:|---:|---:|
| 16 | MeshPotato | White | Win | 107 | 20.412 s | 59.773 s |
| 17 | ChessNotCheckers | Black | Loss | 164 | 2.720 s | 59.357 s |
| 18 | French Carlsen | White | Loss | 141 | 8.531 s | 62.820 s |
| 19 | The big H | White | Win | 32 | 70.153 s | Only 16 decisions |
| 20 | SaucyBeans | Black | Win | 93 | 29.202 s | 59.544 s |
| 21 | The Castle Gambit | Black | Win | 107 | 6.398 s | 70.171 s |
| 22 | CheckmateGPT | White | Draw | 155 | 2.166 s | 62.234 s |
| 23 | OMI | White | Loss | 131 | 2.392 s | 71.057 s |
| 24 | The Huxley Knights | White | Win | 120 | 9.406 s | 61.934 s |
| 25 | keep kann and caro on | Black | Win | 93 | 17.906 s | 66.172 s |

Storm's mean reserve was **16.929 s**, but the short R19 win contributes
70.153 s; excluding it gives **11.015 s**. The three losses averaged only
**4.548 s** left. The other side averaged 19.597 s across all games. The
observed complete first-20 totals average **63.674 s**, population standard
deviation **4.212 s**, with a range of 59.357–71.057 s. Mean time per decision
falls from **3.219 s** on decisions 1–20 to **2.648 s** on 21–40, **1.261 s**
on 41–60 and **0.558 s** after 60. These are wall times inferred from
consecutive PGN clocks with the 0.5 s increment, not rounded log summaries.

The largest move was **26...f5 in R25, 12.246 s**. Initialization ranged from
37.7–45.7 s in the supplied rounded site logs, inside their stated 90 s
budget. Telemetry reports completed selective depths, not equal search
coverage; occasional large depths in nearly forced losing endings do not
imply strong analysis. `t` is search time, `b` is a soft target and neither
is the referee's overall move time nor a hard maximum.

The current live-rule revision is handled in the main Odin review. None of
these ten games approaches the old 284-ply material-mode threshold: the
longest has 164 played plies. The new rule change therefore does not explain
these results.

## Independent reference layer: wins also contain missed opportunities

The parent review ran **Stockfish 19 offline**, one thread, 128 MiB hash,
fresh hash and full available history for each root. The retained file
`lab/odin/reference-deep.jsonl` records the executable/source hashes and
2,000,000-node unrestricted-root searches plus separately constrained
2,000,000-node searches of the move actually played. The engine is an
analysis instrument only; its code and answers are not part of our agent.
The following results were complete when this report was written. Values
are reference pawn units from **Storm's perspective**, not Storm's own
centipawn calibration and not proved game-theoretic values.

| Game / played move | Reference best | Reference root / played | Storm score | Actual think / clock before |
|---|---|---:|---:|---:|
| R16 30.Qd1 | d4 | −3.08 / −5.01 | −35 cp | 1.926 / 63.980 s |
| R17 59...Bf8 | Qg8 | 0.00 / −8.74 | −91 cp | 1.746 / 12.941 s |
| R17 64...Be7 | Ke7 | −0.03 / −5.46 | −198 cp | 0.669 / 10.395 s |
| R18 21.Qd1 | Bd2 | +0.03 / −1.14 | 0 cp | 4.264 / 77.434 s |
| R20 38...f5 | e4 | +4.18 / +0.66 | +141 cp | 2.843 / 49.401 s |
| R23 28.Qe2 | Nf1 | +0.58 / −1.10 | +57 cp | 8.970 / 67.413 s |

This changes the emphasis in two ways. First, R16's eventual win conceals
a position the reference regards as very bad: Storm underestimates the
opponent's queenside pressure and repeatedly overlooks the central `d4`
resource. R20 wins later but passes over a much stronger immediate `...e4`
break. **Central pawn breaks and concrete activity belong beside king
danger in the development set.** Second, R17 appears to offer substantial
defensive chances late in the game. It must not be dismissed as an already
hopeless blockade. At 64...Be7 the reference strongly favors a **quiet king
move**; at 59...Bf8 it favors a **quiet queen defense**. Analyze these with
LMR/selectivity ablations and endgame evaluation before assuming the early
strategic deficit alone caused the final result.

For R22 the reference also finds recoverable drawing chances that Storm
missed: **35.Bxg6** instead of 35.Qd2 gives 0.00 versus −2.38; **72.Rxh2**
instead of 72.Rh8 gives 0.00 versus −2.50 in the retained searches. The
eventual draw therefore includes both defensive success and missed earlier
defensive resources. Preserve the final perpetual while testing those
earlier sacrifices/captures. R23's **28.Qe2** is particularly informative:
Storm already spent 8.970 s / 5.54 million nodes, so a global time multiplier
is an implausible complete solution to that decision.

These moves are **diagnostic labels to verify at increased budgets**, not
an opening book or a requirement that every strong engine choose the
same move. Roots can have multiple adequate moves. The complete main Odin
review incorporates subsequent reference results and should be consulted
before deciding which labels become regression assertions.

## The losses in detail

### R23, OMI: the highest-priority diagnostic

This Nimzo-Indian game stays materially equal through **37...Qh1+**. Storm's
knight maneuvers `18.Nd2 21.Nf1 22.Ng3 24.Ne2 27.Ng3` while Black improves
the knight and queen/rook alignment and advances `...g5`. After
`27...Ne4 28.Qe2 Nxg3 29.fxg3`, White has doubled g-pawns and no f-pawn
shield. `30.h4 Nd6 31.hxg5 hxg5` removes the h-pawn shield and opens the
h-file. Black then plays `32...Ne4 33...Rh6 34...g4 35...Qf5 36...Qh5`.

Storm's recorded opinion and remaining clock before its move:

| Root | Game ply | Own score | Completed depth | Clock before |
|---|---:|---:|---:|---:|
| 27.Ng3 | 38 | +79 cp | 14 | 68.486 s |
| 30.h4 | 44 | +25 cp | 13 | 57.539 s |
| 32.Bf2 | 48 | +10 cp | 12 | 54.103 s |
| 33.Rc2 | 50 | −2 cp | 13 | 51.970 s |
| 34.Qf3 | 52 | −14 cp | 13 | 49.095 s |
| 35.Qe2 | 54 | −195 cp | 17 | 46.682 s |
| 36.Qd3 | 56 | −736 cp | 15 | 45.141 s |

After `37.Kf1 Qh1+ 38.Ke2 Qxg2 39.Rf1 Nxg3+ 40.Ke1 Nxf1`, White has lost
two pawns and a rook before taking the knight back. `41.Bh4 Qf3 42.Qxf1
Qxe3+ 43.Re2 Qc1+ 44.Kf2 Qxf1+ 45.Kxf1 Rxh4` reaches a lost-material rook
ending. Black eventually promotes both queenside pawns and mates.

The crucial inference is about **recognition latency**. Storm had 49 s
before 34.Qf3 and 45 s when its score collapsed; its final 2.392 s reserve
cannot explain why it thought the preceding position approximately equal.
Search selectivity, evaluation, and/or an unrecognized defensive resource
need independent ablation. Do not encode "never play h4" or hard-code a
replacement move from this one game.

Exact roots for independent analysis:

```text
R23 game ply38, before27.Ng3:
r5k1/2nq1p2/2p1rn1p/pp1p2p1/3P4/P3P2P/1PQ1NPP1/2RRB1K1 w - - 0 27
R23 game ply44, before30.h4:
r3n1k1/3q1p2/2p1r2p/pp1p2p1/3P4/P3P1PP/1P2Q1P1/2RRB1K1 w - - 1 30
R23 game ply48, before32.Bf2:
r5k1/3q1p2/2pnr3/pp1p2p1/3P4/P3P1P1/1P2Q1P1/2RRB1K1 w - - 0 32
R23 game ply52, before34.Qf3:
r5k1/3q1p2/2p4r/pp1p2p1/3Pn3/P3P1P1/1PR1QBP1/3R2K1 w - - 4 34
```

### R18, French Carlsen: coordination and pawn structure before material

From a Caro-Kann Advance start, White exchanges both bishops/knights in
ways that leave its remaining bishop and knight defending a central pawn
chain. `19.Bxc6 bxc6`, followed by the queen/rook pawn exchanges through
`24.Rxc6`, restores equal material. Black's rooks and queen then coordinate
against White's position. The sequence `28.Re1 Be4 29.Bc3 Ra3 30.Qd2 Bxf3
31.gxf3 Nf5` leaves White with an exposed king and doubled f-pawns. Black's
rooks reach c4 and b3 while White's rooks and bishop repeatedly defend.

Storm goes from −19 cp at 28.Re1 to −107 at 32.Rc2, −164 at 37.Qe3 and
−256 at 38.Qe2; material remains equal throughout. That makes the earlier
coordination/structure roots more informative than merely diagnosing the
later dropped pawn. At 42.Qd3, Storm already reports −409 cp with 29.257 s
remaining. `42...Nxd4` takes the d-pawn; `45...d4 46.Qa2 Qxa2 47.Rxa2 dxc3
48.Re2 c2` then wins the bishop and creates a seventh-rank passer. Black
converts with `...Rb4–b1`, `...Rxc1`, `...Ne2`, and `...c1=Q`, ultimately
reaching rook and knight against pawns and mating on h3.

There is no basis in the PGN alone to call 42.Qd3 the first losing
move; the independent layer already identifies 21.Qd1 as an earlier
meaningful loss of evaluation. Evaluate earlier exchanges, the Bxf3 recapture choice and rook
activity. A late "passed pawn too valuable" bonus might notice the
symptom while leaving the earlier strategic decisions unchanged.

```text
R18 game ply46, before28.Re1:
r1r3k1/4npp1/4p1bp/1q1pP3/3P4/5N1P/3B1PP1/2RQ1RK1 w - - 7 28
R18 game ply50, before30.Qd2:
2r3k1/4npp1/4p2p/1q1pP3/3Pb3/r1B2N1P/5PP1/2RQR1K1 w - - 11 30
R18 game ply74, before42.Qd3:
2r3k1/5pp1/4p2p/3pPn2/2rP1P2/1qB2Q1P/2R2P1K/2R5 w - - 15 42
```

### R17, ChessNotCheckers: space and a restricted queen/bishop ending

From an English Symmetrical start, White obtains d5/e4 space and an open
a-file with `15.a4`, `19.a5`, and `20.axb6 axb6`. `21.Ra7` puts a rook on
the seventh. Storm exchanges `21...Nxe3` and `23...Bxe4`; White's remaining
bishop and heavy pieces continue to control the queenside. By `34.Raa7`
both white rooks are on the seventh rank. At `38...e6`, Storm scores itself
−175 cp and spends 5.101 s from a 38.185 s clock. White immediately creates
`39.d6`, followed by `42.d7`; the pawn remains on d7 through move 70.

After rook exchanges, Black often has one extra pawn but its queen is
occupied blockading d7, its bishop lacks activity, and White's queen and
bishop can attack from outside that blockade. The late sequence is
`63.Bb3 Bc5 64.Qc8 Be7 65.c5 bxc5 66.Qc6 Kg7 67.Qxe6 e4 68.Qf7+ Kh8
69.Qe8+ Kg7 70.Bg8 Qxd7+ 71.Qxd7 Kxg8 72.Qxe7`. The game ends with White
having a queen against Black's pawns; Black's eventual f-pawn promotion is
captured, and White promotes another queen before mating.

Storm's reported scores oscillate around −0.75 to −1.6 during much of the
long blockade, fall to −247 cp at 66...Kg7, and reach −995 by 69...Kg7.
The PGN and telemetry point toward evaluating restriction, blockading cost
and king/pawn coordination. The independent layer above additionally finds
near-equal alternatives in the queen/bishop ending; preserve those concrete
quiet defenses as search and evaluation diagnostics.

```text
R17 game ply23, before18...b6:
2qr1rk1/pp1bp1bp/6p1/2pPpn2/P1P1N3/3QB1PP/1P3PBK/R4R2 b - - 1 18
R17 game ply63, before38...e6:
1r1r1bk1/R3p2p/1pR2qp1/3Pp3/1QP1B2P/5PP1/8/6K1 b - - 2 38
R17 game ply115, before64...Be7:
2Qq4/3P1k2/1p2p2p/2b1p2p/2P5/1B3PPK/8/8 b - - 27 64
```

## The draw is a defensive success to preserve

R22, against CheckmateGPT in the Two Knights Defence, is **not evidence of
throwing away an obvious win by repetition**. Storm's highest reported
score in the entire game is only +58 cp. Black's `28...Rxc3` exchanges a
rook for a knight, with `29.bxc3 Bxc3` recovering the pawn and gaining
activity. The advanced a-pawn reaches a3. After the queens and one pair of
bishops are exchanged, White has two rooks against rook, bishop and an
extra pawn: superficially a small material surplus by P1/N3/B3/R5/Q9, with
considerable dynamic compensation for Black.

White's rooks become occupied with the passers while Black's king becomes
active. By `72.Rh8`, Black has pawns on **a2, d2 and h2**. White takes d2,
checks the king repeatedly, takes a2, and allows `79...h1=Q`, reaching two
rooks against queen and rook. `80.Ra3+ Kg2 81.Rg4+ Kh2 82.Rh4+ Kg2
83.Rg4+ Kh2 84.Rh4+ Kg2` gives a perpetual checking pattern.

The final position is only its **second** occurrence. The next legal move
`85.Rg4+` (`h4g4`) would create the third occurrence, so
`outcome(claim_draw=True)` already returns a draw before White is asked to
move. The replay confirms that exact mechanism. Preserve this full-history
sequence as a regression, especially when changing repetition policy,
material optimism, passed-pawn evaluation, or "avoid draw when winning"
logic. Do not force a winning attempt merely because raw material was
temporarily positive before promotion.

## The six wins identify strengths Odin must preserve

**R16, MeshPotato, Sicilian Closed.** White initially accepts substantial
black rook activity on the b-file. `32.Re2 Rxe2 33.Qxb3` captures the other
black rook and restores equal material; `36.Nxe6+` and `38.Qxd6` start
useful forcing play.
Storm handles the dangerous d2 passer through `47.Kh2`, later takes it on
d2, and takes the bishop on a6. It does not confuse its material advantage
with permission to ignore checks: the longest decision is **53.Qg2,
5.648 s**. It finds a mate score at **54.g6+**, then rapidly plays
`Ra8+`, `Qa2+`, `Rxf8`, `Qe6+`, `Rf7+`, `Qe8#`. The final 20.412 s is a
consequence of finishing a proven attack, not evidence of unused capacity
before the decisive choice.

**R19, The big H, Caro-Kann Exchange.** Black castles long into a damaged
queenside and advances the kingside pawns. White combines `Bb5`, `Ne5`,
`Bxc6`, and a knight route via d3 to c5. Storm's material-plus-attack score
reaches +799 at **19.Nd3**, its 9.868 s decision. It finds a mate score at
**21.Qb3** and executes `Qb7+ Nxe6+ Qc7#`. This 16-decision game ends with
70.153 s, a useful positive control for early stopping on a mate proof.

**R20, SaucyBeans, Sicilian Classical.** Black builds a central pawn mass
and active bishop/rook coordination. After White gives an exchange with
`36.Rd5 Bxd5 37.exd5`, Black plays `...f5`, `...e4`, `...e3`, and `...e2`.
Storm's score is +801 at **45...Re3** despite equal raw material at that
root: it correctly sees the advanced pawn and attack through search.
**46...Rxg3+** is the first logged mate proof, followed by forced play to
`52...Qxh4#`. This directly argues against portraying Storm as incapable
of understanding every advanced passer; the aim is earlier and more
reliable recognition under tighter search horizons.

**R21, The Castle Gambit, Sicilian Closed.** Black collects a5 and steadily
improves the queenside position with doubled rooks and a b-pawn advance.
`36...Rxb3`, `38...b3`, `40...Nh5`, and **41...Nf4** combine threats on both
wings. The exchanges through `43.Rxf4 Rxf2 44.R4xf2 Rc2 45.Bf3 Rxf2 46.Kxf2
b2` give Black a decisive queen/passer combination. Storm promotes and
mates on h2. It uses almost its entire original time allocation before
finding a mate proof at **56...g4**; its final reserve is 6.398 s. Preserve
this conversion and cross-board calculation while modifying king safety.

**R24, The Huxley Knights, Sicilian Sveshnikov.** A long materially equal
middlegame reaches two rooks and knight against two rooks and bishop.
After **48.b5**, White's knight route `Nb6–a4–c5–b7–d6–f7` supports the
b-pawn. `55.b6`, `60.b7`, and `61.bxa8=Q` turn the passed pawn into material.
Storm finds a mate proof at **64.Rbb7** and mates with `68.Rh7#`. This is a
successful nontrivial endgame conversion; keep its key positions as positive
controls when adding bishop-pair, mobility, king activity, or pawn terms.

**R25, keep kann and caro on, Caro-Kann Classical.** Black obtains an
outpost with `21...Nd3` and starts a central/kingside break with
**26...f5**, its 12.246 s maximum think. White's b-pawn reaches b6, but
Black combines active heavy pieces, `...f4` and the knight. The black king
walks through h7/g6 in a position where Storm nevertheless maintains an
advantage in its own analysis; a naive king-distance penalty could reject
good active play. After `40...Nf4 41.Qf5+ Kh6 42.Qxf4 gxf4`, Black has a
decisive queen-versus-rook advantage, takes b6, and finds a mate proof at
**47...Rb1**, eventually mating on f3.

## Concrete implementation implications for Odin

1. **Make king danger the first evaluation experiment.** Build an explicit
   tapered, queen-sensitive model using pawn shelter, open/semi-open files
   near the king, enemy attack units entering the king zone, and safe
   checking access. Build reusable attack maps rather than repeated legal
   move generation per evaluation. Validate color/rank symmetry, pinned
   attackers and make/unmake invariants. Calibrate on a broad independent
   corpus; do not tune coefficients to force the 44 selected roots. Test
   R23 before the score collapse, plus the R16/R19/R21/R25 wins so the model
   does not become indiscriminately timid.
2. **Add piece mobility, rook activity and structured pawn evaluation as
   separately measurable changes.** Safe mobility should exclude enemy
   pawn-controlled squares; rook activity should recognize useful open
   files and seventh-rank penetration. Pawn terms should distinguish
   isolated/backward or doubled weaknesses from a useful passed pawn,
   include rank, blockade, protection, promotion-square access and king
   distance in appropriate phases. R17 and R18 justify evaluating the
   position before material falls; R22 requires respecting defensive
   resources and dangerous enemy passers even when up raw material.
3. **Diagnose search before assuming a static evaluator alone fixes it.**
   At independently analyzed R23 roots, compare current search, reduced
   selectivity, and additional node budgets using the same evaluation.
   If a quiet defense/attack is only found without reduction, target LMR,
   quiet-move ordering and verification, preserving full-depth re-search.
   If all versions search deeper into the same wrong score, prioritize
   evaluation. Keep history intact for repetition-sensitive R22 roots.
4. **Treat clock improvements as a later, measured component.** Storm
   already varies effort, returns forced moves immediately, and often
   uses almost all useful time in long games. An evaluator that fails to
   notice danger may also fail to request time. Consider root uncertainty,
   second-best separation and instability as additional signals only
   after recording them. Compare fixed-evaluation clock ablations under
   the full 120+0.5 wall clock; never demand an empty clock as a target.
5. **Use these as diagnostics, not a ten-game training-and-test set.**
   Include full histories and positive controls; separate score agreement,
   correct best moves, and playing strength. The acceptance match must
   use fresh realistic curated openings, both colors, against frozen
   Storm, with native Linux timing and an immutable candidate. The 65%
   site score and 82.5% local-v3 score concern different opponents and
   opening distributions and are not directly comparable Elo estimates.

Do not ship any particular coefficient, pruning rule, or extra term merely
because it appears in this list. Each experiment needs an isolated native
cost measurement, correctness checks for the state it changes, independent
position evidence and paired match evidence. The intended direction is a
better-informed and better-validated searcher, not hard-coded repairs to
these ten games.
