# Storm: day-one game forensics

Source: all 15 PGNs and companion platform logs in `Chess_results_day1`, representing the deployed v1. Public leaderboard fetched directly at **2026-09-04 22:37:22 UTC**, with a `no-cache, no-store` response. This report does not attribute v1's mistakes to v3.

## Findings that change the development priorities

**The user's clock concern is supported, and the unused reserve is larger than estimated.** V1 finished with **33.535 seconds on average**, median **29.521 seconds**. The five losses ended with **30.510 seconds on average**. More revealingly, its first 20 decisions consumed **58.557 seconds on average with only 0.882 seconds standard deviation** across all 15 games. The minimum was 57.27 seconds and the maximum 60.11. The opponents' corresponding totals varied from 31.06 to 97.03 seconds. That is strong evidence that v1's allocation responds too little to differences between games. It is not proof that spending every remaining second would improve the chosen moves.

**Spending more time is one part of Storm, not the whole explanation for stronger play.** Omega3 fish and Keresight spent approximately 89 seconds on their first 20 decisions and beat v1. However, Tobias Carlsen beat v1 after spending only **31.06 seconds**, against our **57.27**, and finished with **60.492 seconds** remaining. Stonkfish also beat us while spending less time overall and in the first 20 decisions. The game evidence supports improving search and evaluation alongside allocation. It cannot identify whether any rival uses a neural network, tablebases, reductions, extensions, or a particular evaluator.

**The gap to the leaderboard leaders remains substantial and unmeasured head to head.** The current snapshot places Samson at **60/243, rating 1685**, with **8 wins, 2 draws, 5 losses**. The leader is rated 2164. None of our 15 opponents is currently in the top 25. These are current ladder ratings, not the ratings before each game; the games also need not represent each rival's current upload. Our sample does not establish performance against the leaders, and the leaderboard alone does not establish that they played exclusively top opponents. [Live leaderboard](https://aichessathon.com/leaderboard).

**These were chess losses, not operational losses.** All five losses were legal checkmates. The two draws were automatic threefold claims. No game reached 300 plies; the longest had 154 plies from its supplied start FEN. No fifty-move or material-adjudication result appears in this sample. All 1,712 plies replay legally, and all 857 own moves and clocks agree with the companion logs within their printed rounding.

## Complete game and clock inventory

Times are seconds. “First 20” means each player's first 20 decisions from the supplied curated position, not fullmove number 20. “Left” is the final recorded post-increment clock. W-D-L order is wins, draws, losses.

| R | Opponent team | Current rank/rating | Result | Our moves | Our left | Their left | First 20 ours/theirs |
|---:|---|---:|:---:|---:|---:|---:|---:|
| 1 | Brownies | 168 / 1361 | W | 35 | 53.58 | 35.21 | 58.25 / 72.66 |
| 2 | omega3 fish | 27 / 1813 | L | 66 | 26.66 | 5.63 | 59.48 / 89.72 |
| 3 | Fork 72 | 88 / 1586 | W | 40 | 47.88 | 33.80 | 58.86 / 70.36 |
| 4 | TheROOK | 26 / 1818 | L | 73 | 24.87 | 8.94 | 57.73 / 57.12 |
| 5 | Baryon | 79 / 1610 | W | 55 | 30.87 | 43.83 | 58.75 / 46.74 |
| 6 | Stonkfish | 56 / 1696 | L | 59 | 31.61 | 40.83 | 58.03 / 53.91 |
| 7 | LehmanBro | 54 / 1702 | W | 58 | 31.29 | 3.05 | 60.11 / 97.03 |
| 8 | lefischer | 132 / 1468 | W | 60 | 29.52 | 18.62 | 59.20 / 70.10 |
| 9 | Tobias Carlsen | 102 / 1538 | L | 42 | 46.43 | 60.49 | 57.27 / 31.06 |
| 10 | DGS ELO | 91 / 1582 | D | 57 | 27.80 | 22.80 | 58.80 / 63.86 |
| 11 | TriggerFish | 89 / 1584 | W | 65 | 26.72 | 14.49 | 57.99 / 84.38 |
| 12 | Keresight | 76 / 1635 | L | 75 | 22.98 | 7.37 | 58.95 / 88.81 |
| 13 | Desai | 62 / 1680 | W | 77 | 23.73 | 4.24 | 60.03 / 87.23 |
| 14 | Sillycats | 74 / 1647 | W | 61 | 28.46 | 27.57 | 57.33 / 62.19 |
| 15 | bitter1 | 57 / 1694 | D | 34 | 50.63 | 57.54 | 57.59 / 53.78 |

The official page uses bot names that can differ from the exported opponent team names. `leaderboard_comparison.json` preserves both names and each team's public URL. Snapshot top five: [SoberJackson](https://aichessathon.com/team/258a9828-7442-4bea-97cb-eed1845ad2cc?from=lb), 2164, 12-1-2; [ms](https://aichessathon.com/team/c3e1bc09-3d21-4279-ace0-16bb3742f5da?from=lb), 2132, 11-2-2; [Mate in One](https://aichessathon.com/team/3be637a8-e78d-4da4-8016-d13e00170433?from=lb), 2125, 10-4-1; [Patzer 1.2](https://aichessathon.com/team/3f0e0e44-cdce-485f-b5b6-3691e34f9f44?from=lb), 2080, 11-1-3; [checkers](https://aichessathon.com/team/9e5e613a-ca80-4fd9-aa68-76f184ef7bac?from=lb), 2026, 9-3-3. All had 15 recorded games. These observations come from the saved [leaderboard](https://aichessathon.com/leaderboard) snapshot; no rival source code was available.

## What the move sequences suggest testing

These are concrete investigation points, not claims of optimal play or engine-certified blunders. Material counts use P1 N3 B3 R5 Q9 and are not evaluations. An intermediate capture may be recaptured or compensated, so a one-turn material swing must not be used as a training label.

**R2, omega3 fish: exposed king and forcing attack.** Our 20.g4 precedes the opposing knights' invasion. The sequence from 30...Qf4 through 32...Nxf2, 33...Nh3+, and rook checks forces defensive coordination. At **38.Rf2**, we spent **1.667 seconds with 54.902 seconds available**; the continuation was 38...Rxe2 39.Rxe2, exchanging our queen for the opposing rook. It is not established that 38.Rf2 is the first error or that a saving alternative exists. The useful diagnostic positions begin several moves earlier, at 20, 23, 30, 32, 37 and 38. This is a test for defensive tactical search and king safety, not just extra time on the final visible loss of material.

**R4, TheROOK: compensation and passed-pawn blockade.** The early 10...Bd7 11.Bxb7 a6 12.Bxa8 Qxa8 sequence requires understanding compensation rather than counting the exchange alone. The later queenside blockade fails against connected passers: 54.a6 Re7 55.a7 Rxa7 56.bxa7 Qxa7 57.b6. Storm should be compared before the blockade breaks, including our 28th, 53rd and 54th fullmoves. After passers become unstoppable, additional time has much less value.

**R6, Stonkfish: king activity and the pawn-ending horizon.** The opposing king advances through e5, f4 and g3 in a rook ending. After 50...Rd2+ 51.Rxd2 exd2 52.Kxd2 Kf3, material is equal. Our **53.Ke1** takes **1.214 seconds with 39.240 seconds available**. The enemy king reaches g2 and supports the g-pawn to promotion. This is a useful case for passed pawns, king activity, and searching the consequences of a rook trade. Equal material is plainly not a sufficient description of the resulting ending. Probe 34, 39, 50, 51 and 53, not only the promotion position.

**R9, Tobias Carlsen: active pieces and king attack despite our material.** At our **23.Qa4** we are two material points ahead, but the reply ...Rd2 invades the second rank. Our 24.g3 is followed by ...Bxe7, and subsequent play brings ...f4, ...Bh3 and ...Rg2+. We spent 2.944 seconds on 23.Qa4 with 84.031 seconds available and 2.188 seconds on 24.g3 with 81.587 available. The corpus includes the earlier central capture sequence and the positions before the king attack. This loss is a particularly useful counterexample to the theory that every stronger rival simply spends more time early.

**R12, Keresight: forcing simplification into a rook ending.** The queen-exchange sequence includes 18...Qe4 19.Qxe4 Bc3+ 20.Kd1 Nxe4; the apparent temporary nine-point material surplus is not a queen win. After ...Nxf2+ and rook activity, the opponent activates its king and eventually advances connected g/h passers. Early tactical roots and the rook ending at 30, 51 and 64 are included. This combines forcing checks, activity, and long-term passed-pawn consequences. Its 88.81-second first-20 investment versus our 58.95 is consistent with aggressive early allocation, but the PGN cannot distinguish a deliberate criticality model from a different ordinary time formula.

**R10, DGS ELO: a draw with material ahead is not necessarily a lost win.** We finish two material points ahead while delivering queen checks, but the opponent has a protected pawn on c7 and another on d6. The late Qd2+/Qc1+ cycle merits a history-aware search comparison, not automatic rejection of the draw. The final position is only a second occurrence; `can_claim_threefold_repetition()` is already true because a legal next move completes threefold. The referee therefore stops before asking us for another move. Best-move labels require proper analysis of the whole position, including the advanced passers.

**R15, bitter1: repetition from material inferiority.** The exchange/knight-sacrifice sequence beginning 14...Nxd5 and 16...Nxg2 leaves us two material points down by the eventual bishop shuffle. The final Bf8/Bh6 and opposing queen sequence triggers the same claim-by-next-move mechanism: the current position itself is not threefold. The 50.630-second reserve is real, but the PGN does not establish that declining the draw improves our result.

## Clock strategy supported by the evidence

The first-20 near-constant is a stronger actionable signal than final time alone. A game can finish early with a rational reserve, and a forced mate can return essentially instantly while collecting increments. In these logs the terminal reserve averages 34.005 seconds for wins, 39.217 for draws and 30.510 for losses. The objective should be to improve decisions at a fixed total clock, not minimize the final clock retrospectively.

The data suggests testing an allocation policy that grants more time when successive iterations change the preferred move, the score deteriorates, or the root remains difficult to resolve; it should save time on stable moves, easy forced replies and completed mate proofs. We observed **14 own positions with exactly one legal move consuming 14.817 seconds in total**, another concrete source of recoverable time. The PGNs do not expose iteration scores, principal variations, node shares or completed depths, so which internal signal works best must be measured in Storm's own traces.

Use time-only and search-only comparisons against v3 before interpreting their combined gain. A higher node rate, a deeper reported depth, or less unused time is not itself an improvement in chess quality. For the ambitious Storm branch, the relevant question is whether better ordering and selective search solve more of these tactical/positional problems at the same budget, and whether that carries to held-out paired games. These observed games are development material, not the holdout that decides promotion.

## Reproduction and diagnostic corpus

From the repository root, using the already-installed Python 3.12 environment:

```powershell
& 'C:\Users\finla\AppData\Local\ChessTK\venv312\Scripts\python.exe' lab/storm/analyze_games.py
& 'C:\Users\finla\AppData\Local\ChessTK\venv312\Scripts\python.exe' lab/storm/fetch_leaderboard.py --offline
```

The first command replays every PGN, checks legal moves and final outcomes, compares the exact clocks and SAN against all companion logs, and regenerates:

- `lab/storm/day1_summary.json`: game metadata, timings, material and repetition details, and source hashes.
- `lab/storm/day1_games.csv`: compact complete comparison table.
- `lab/storm/day1_moves.jsonl`: all 1,712 decision positions, clocks, actual moves and full supplied-game histories.
- `lab/storm/day1_diagnostics.jsonl`: **163 selected roots**, including all seven non-win case studies, phase transitions, largest time investments, material-transition triggers and repetition histories. Every root is explicitly unlabelled; `best_move_uci` is null.
- `lab/storm/day1_diagnostics.fen`: convenient FEN-only view of those roots.

For repetition-sensitive comparisons, use the JSONL's `start_fen` plus `history_uci`; a FEN alone loses the information that produced both draws. `game_ply` counts from the supplied game FEN and differs from the FEN's fullmove number. There are 14 distinct start FENs: rounds 4 and 10 share the English Symmetrical position.

The leaderboard command re-parses the saved HTML. Omitting `--offline` deliberately refreshes the snapshot and its metadata. `leaderboard_comparison.json` records the top five, Samson and every opponent, together with source URL, retrieval time, server date, cache headers and SHA-256. Refreshing the data can naturally change the rankings quoted above.

No Stockfish or other external engine was run, no reference engine's labels were fabricated, no dependencies were installed, and no engine source or official harness was modified for this analysis. The game logs show a 90-second initialization budget; old 60-second doctrine should not be used to override the live contract. The root task is verifying the current contract separately.

## Supplementary coverage review for the v4 holdout

The predeclared native r2 holdout uses synthetic opening indices 160–179 from `lab/openings.fen`, with each colour played from each FEN. A direct comparison with the 14 distinct site starts found a material difference in development and king placement:

| Feature | All 200 synthetic starts | Holdout 160–179 | 14 unique site starts |
|---|---:|---:|---:|
| Mean minor pieces off their own back rank | 1.52 | 1.40 | 4.21 |
| Starts with a king on a c/g home-rank square | 0 | 0 | 4 |
| Starts in check | 29 | 7 | 0 |
| Mean FEN fullmove number | 5.64 | 5.50 | 6.79 |
| Mean remaining pieces | 30.91 | 31.30 | 30.86 |

Definitions: “minor pieces off their own back rank” counts the currently present White bishops/knights outside rank 1 plus Black bishops/knights outside rank 8; captured pieces contribute zero. King placement counts a White king on c1/g1 or Black king on c8/g8. That is a FEN feature, not a general proof that a castling move occurred. “In check” uses `chess.Board(fen).is_check()` for the side to move. Means weight each distinct FEN once. The synthetic and site sets have no exact FEN overlap. Fullmove numbers describe the starting positions; the engine must still count actual served game plies for the referee cap.

The synthetic generator rewards captures, checks and central squares early. Its near-starting material counts do not imply development comparable to the site's curated openings. The existing holdout remains a valid comparison on its declared corpus; this difference limits how confidently its effect size can be projected onto the tournament.

The chosen supplementary check is **two full-clock colour pairs**, from zero-based `lab/storm/site_openings.fen` indices **8 and 10**:

1. Round 9, **Two Knights Defence**, both kings already castled and five minor pieces off their back ranks: `r1bq1rk1/ppp1bppp/2np1n2/4p3/P1B1P3/2PP1N2/1P3PPP/RNBQ1RK1 b - - 0 7`.
2. Round 12, **King's Indian Classical**, a later start with seven minor pieces off their back ranks: `r1b1qrk1/ppp2pbp/n2p2p1/4p1B1/2PPP1n1/2NQ1N2/PP2BPPP/R3K2R w KQ - 6 10`.

These starts were selected to exercise specific coverage gaps, and they were already observed during development. The root task will run them locally while the native holdout continues. They are supplementary stress evidence, not independent native promotion evidence; retain their machine/runtime limitations and keep them out of the native holdout confidence interval. Do not replace any predeclared holdout positions or results with them.

The independent scoring/provenance review is recorded in `docs/STORM_MATCH_EVIDENCE_REVIEW.md`.

## Public timing evidence from the current leader

The saved leaderboard identifies **SoberJackson / Sobriety**, team ID `258a9828-7442-4bea-97cb-eed1845ad2cc`, as the leader. Its public [team page](https://aichessathon.com/team/258a9828-7442-4bea-97cb-eed1845ad2cc?from=lb) was fetched at **2026-09-04 23:21:16 UTC**. The three newest listed games, rated rounds 15, 14 and 13, each expose a visible PGN download containing exact move-clock annotations. Those public downloads were decoded and legally replayed; no private endpoint, authentication, reference engine, or hidden search data was used.

These games confirm that a leading engine can make selective longer investments and then accelerate. They also show that its success does not require exhausting the bank or spending more total time early than v1:

| Leader game | Opponent's snapshot rank/rating | Result | Leader moves | First 20 thinking | Opponent first 20 | Leader final clock |
|---|---:|:---:|---:|---:|---:|---:|
| [R15, No More Ammo](https://aichessathon.com/game/ed18ab9c-b4ad-4f29-a6ea-f9e53bc3f2e8?from=t.258a9828-7442-4bea-97cb-eed1845ad2cc) | 8 / 1947 | W | 50 | 45.122 s | 75.570 s | 65.440 s |
| [R14, pheanup](https://aichessathon.com/game/d29de303-2935-4ec9-9ccf-e0029ddbc409?from=t.258a9828-7442-4bea-97cb-eed1845ad2cc) | 10 / 1937 | W | 60 | 52.819 s | 87.154 s | 45.568 s |
| [R13, Mate in One](https://aichessathon.com/game/f6ca50df-b9a4-48e9-b092-e5ea7896030a?from=t.258a9828-7442-4bea-97cb-eed1845ad2cc) | 3 / 2125 | D | 112 | 49.527 s | 71.922 s | 22.741 s |

Ranks/ratings are from the independently saved 22:37 UTC [leaderboard](https://aichessathon.com/leaderboard), not pregame ratings. The latest three opponents were strong at that snapshot; this does not establish that every earlier opponent was similarly ranked. Round 13 ended under the fifty-move rule; the other two ended in checkmate.

Across these three games, SoberJackson spent **49.156 seconds on its first 20 decisions**, standard deviation **3.153 seconds**, and retained **44.583 seconds at the end on average**. Our v1's 15-game values were **58.557 seconds**, **0.882 seconds** and **33.535 seconds**, respectively. Different game lengths, openings and opponents prevent interpreting this as a controlled policy comparison. The observed leader's large reserves nevertheless make “unused seconds necessarily explain the strength gap” untenable as a general explanation.

The within-game timing is more informative than the reserve alone. Mean seconds per leader decision by its own move count:

| Game | Decisions 1–10 | 11–20 | 21–40 | 41–60 | 61 onward |
|---|---:|---:|---:|---:|---:|
| R15 | 2.332 | 2.180 | 1.532 | 0.380 | — |
| R14 | 3.104 | 2.178 | 1.683 | 0.898 | — |
| R13 | 1.704 | 3.249 | 1.737 | 1.396 | 0.790 |

Round 13 specifically shifts more time into decisions 11–20 than the first ten. The longest decisions were **7.432 seconds on 17.Be3** in round 15, **7.118 seconds on 14...Nf6** in round 14, and **6.115 seconds on 30.g6** in round 13. Conversely, round 15's first 8.d4 took just **3 ms**, and each winning game contained eight decisions below 100 ms. These are measured timing facts; they do not reveal whether an individual fast move came from an opening choice, forced result, cache, search stopping condition, or something else. No internal depth, node count, evaluation or rival algorithm was exposed.

The engineering implication is to measure both selective use of time and decision quality per unit of time. The data supports spending longer on selected unresolved decisions and returning quickly when the decision is settled. It provides no basis for claiming that a sophisticated time controller alone explains the leader's strength, or that using all remaining seconds is the right objective.

Reproduce the numbers offline with:

```powershell
& 'C:\Users\finla\AppData\Local\ChessTK\venv312\Scripts\python.exe' lab/storm/analyze_leader.py
```

The saved public HTML, retrieval metadata and SHA-256 hashes are in `lab/storm/soberjackson_*`. `soberjackson_round_13.pgn`, `_14.pgn` and `_15.pgn` preserve the visible PGN downloads; `soberjackson_moves.jsonl` contains every reconstructed decision and clock; `soberjackson_summary.json` records source URLs and computed aggregates. PGN player headers are placeholders, so player colour and opponent identity are checked against the public team table. The sample is exactly the three newest games at the recorded retrieval time, with no outcome-based selection.
