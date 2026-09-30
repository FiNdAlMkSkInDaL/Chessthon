# Storm review and the case for Odin

Reviewed 5 September 2026. **Odin should retain Storm's tested search foundation
and improve the decisions it searches: legal exchanges, drawing resources,
quiet defence, king danger and pawn/rook coordination. Increasing every move's
time budget is not supported by these games.** The precise implementation
assignment is `ODIN_BUILD_BRIEF.md`; the revised continuation prompt is
`STORM_CONTINUATION_PROMPT.md`.

This review changed documentation and analysis tools only. Storm's deployed
source and the signer archive (not in git) are unchanged. Odin has not been implemented,
tested as a playing agent, or submitted.

## Scope and evidence

- All ten supplied site PGNs and logs, rounds 16–25: **6 wins, 1 draw, 3 losses**,
  65% score; 1,143 legally replayed plies, 572 Storm decisions, 558 matched
  `S4` telemetry records. The other 14 decisions were forced legal replies.
- All 40 native full-clock Storm-v3 games: **31 wins, 4 draws, 5 losses**,
  82.5% score; 5,028 legally replayed plies. The original fixed paired
  confidence interval remains 71.25–92.5%, not a predicted leaderboard rating.
- The eight short-clock screen games and four supplementary site-opening
  games remain separate. Their respective records were 8–0 and 1 win/3 draws.
- Independent offline Stockfish 19 screening of **6,221 positions across the
  main 50 games**, including starts and terminal positions: 100,000 nodes per
  site position and 50,000 per native-match position. Then 34 selected roots
  at 2 million nodes per unrestricted/played-root search, and 15 key roots
  reconfirmed at 5 million nodes per call with individual UCI score events.
- A seven-piece tablebase check, controlled cold-TT Storm probes at 3/9 seconds,
  and source-isolated reproductions of exchange/draw helpers.

The user identifies the site upload as Storm; the logs contain expected S4
telemetry but no archive hash. Exact archive identity is proven for the local
release/matches, not independently by the site logs. The offline reference
binary was obtained from the official [Stockfish 19 release](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19),
hash-verified, and kept outside the repository under the local analysis tools.
No external engine code or reference network was added to our submission.

## The ten site games

| Round | Opponent | Result | Clock left | Main lesson |
|---|---|---|---:|---|
| 16 | MeshPotato | Win | 20.412 s | A win concealed a poor position: repeated missed `d4` breaks and slow queen manoeuvres allowed serious pressure before the opponent erred. |
| 17 | ChessNotCheckers | Loss | 2.720 s | Early restriction and a passer were followed by late defensive chances: `59...Qg8` and `64...Ke7` deserve direct search tests. |
| 18 | French Carlsen | Loss | 8.531 s | Piece coordination deteriorated before material collapsed. At move 21, `Bd2` is a stronger reference continuation than the retreat `Qd1`. |
| 19 | The big H | Win | 70.153 s | Good fast tactical conversion. Preserve it; this short game distorts the average unused clock. |
| 20 | SaucyBeans | Win | 29.202 s | The eventual passed-pawn win was strong, but `38...f5` gave away much of an advantage that `...e4` maintained. |
| 21 | The Castle Gambit | Win | 6.398 s | Strong eventual tactical conversion, with an earlier missed opportunity: `33...Rc3` released an advantage compared with `...Rb7`. |
| 22 | CheckmateGPT | Draw | 2.166 s | The final perpetual was a useful save. Earlier `35.Bxg6` and `72.Rxh2` were better defensive resources than the played moves. |
| 23 | OMI | Loss | 2.392 s | Clearest king-danger case: missed quiet repair `28.Nf1`, then `30.h4` and opening the h-file made the attack much worse. |
| 24 | The Huxley Knights | Win | 9.406 s | A comparatively controlled win; retain its conversion as a regression control. `29.Ne3` is a smaller improvement lead. |
| 25 | keep kann and caro on | Win | 17.906 s | Active knight/rook play and a successful king walk led to a mating attack. Do not make new king safety indiscriminately punish active kings. |

All nine decisive games ended in checkmate, with no operational losses. R22
was correctly stopped by a prospective threefold: the final position itself
was only a second occurrence, but an available next `Rg4+` would complete the
third. A policy that always refuses repetition while materially ahead would
damage precisely this kind of defensive result.

Mean remaining time was 16.929 seconds, but falls to 11.015 excluding R19.
The three losses averaged **4.548 seconds left**. Forced replies already cost
only **0.030 seconds combined**. Storm's time allocation is doing useful work;
the remaining problem is recognizing which decisions and continuations matter.
R23's `28.Qe2` took **8.970 seconds from a 67.413-second clock**, yet its own
completed depth-15 score was +57 cp. The error arose well before final time
pressure. The longest site import was 45.7 seconds against a 90-second limit.

## Independent checks of the important decisions

These are the eleven final site **5-million-node** reference comparisons, from Storm's
perspective in pawn units. Each compares an unrestricted search with a separate
search constrained to the actual played move. Both receive the full recorded
history and a cleared hash. Figures are finite-budget estimates, not proofs
of game-theoretic value or forecasts of platform win probability.

| Decision | Reference alternative | Best estimate | Played-move estimate |
|---|---|---:|---:|
| R16 `24.Qe2` | `d4` | 0.00 | -0.72 |
| R16 `30.Qd1` | `d4` | -2.93 | -4.79 |
| R17 `59...Bf8` | `Qg8` | 0.00 | -9.36 |
| R17 `64...Be7` | `Ke7` | 0.00 | -5.03 |
| R18 `21.Qd1` | `Bd2` | +0.03 | -0.97 |
| R20 `38...f5` | `e4` | +4.25 | +0.64 |
| R21 `33...Rc3` | `Rb7` | +3.84 | 0.00 |
| R22 `35.Qd2` | `Bxg6` | 0.00 | -3.05 |
| R22 `72.Rh8` | `Rxh2` | 0.00 | -2.69 |
| R23 `28.Qe2` | `Nf1` | +0.65 | -0.92 |
| R23 `30.h4` | `Bd2` | -1.09 | -2.59 |

R17 is therefore not simply an inevitable loss after an early disadvantage:
the reference finds later saving chances. R23's `34.Qf3`, initially suspicious
from the telemetry collapse, is already in a very bad position and was also
the best move in the earlier reference pass. The investigation should focus
on the earlier decisions that allowed the attack, not label the move where
Storm finally noticed its danger as the original mistake.

Controlled probes reinforce that direction. With the original Storm source,
full known histories and cold TT/heuristics, both 3-second and 9-second searches
retain R17's `Bf8`/`Be7`, R23's `h4`, and R16's `Qe2`. These probes are Windows
development evidence, with different machine/TT state from the site; they do
not reproduce every original choice. They do show that a blanket longer
allowance is not a demonstrated repair. Data: `lab/odin/storm_diagnostics.json`.

## What the v3 match adds

Storm's 31–4–5 remains a clear local improvement. The all-game ledger and the
five losses/four draws are in `ODIN_HOLDOUT_REVIEW.md`. The five losses averaged
only **3.968 seconds remaining**, so these are not a reservoir of unused time
waiting to be spent.

However, the old opening generator is unsuitable as the primary Odin test.
Some starts contain hanging pieces: opening 166 permits `dxc5` winning a
knight and opening 167 permits `Qxe6` winning a bishop. The low-node independent
screen put seven of the twenty starts beyond one pawn and six beyond two,
with the largest around eight pawns. These are rough screening estimates,
but the immediate material tactics are directly replayable.

This does not invalidate the paired score or explain it away. Descriptively,
Storm was **21–4–1** on the thirteen opening pairs screened within one pawn,
and **10–0–4** on the other seven. This post-hoc split is not a new promotion
test or confidence interval. The lesson is to preserve the observed gain
while using realistic, independently balanced starts for the successor.

The most actionable native loss is opening 165 with Storm Black. Before
`83...Rf4`, the position is:

`2k5/4K3/6P1/8/4p3/5r1p/R7/8 b - - 5 83`

The [Lichess tablebase](https://tablebase.lichess.ovh/standard?fen=2k5%2F4K3%2F6P1%2F8%2F4p3%2F5r1p%2FR7%2F8%20b%20-%20-%205%2083)
classifies it as drawn. `Rg3`, `h2`, `e3`, `Kb7` and `Kc7` preserve that
classification; `Rf4` gives White a tablebase win. Categories for individual
moves refer to the resulting side to move. The tablebase does not encode the
PGN's repetition history; immediate claim status was checked separately.

Storm's static +88 classifier excludes `Rg3` before searching because it
returns to a previously seen position. The four other drawing moves survive,
so filtering did not mechanically force every remaining option to lose.
But a controlled 3/9-second probe is revealing: with the filtered roots Storm
chooses `h2` at three seconds and `Rf4` at nine; with all legal roots it chooses
`Rg3`, score zero, at both budgets. This justifies repairing the root policy
and valuation together. Evidence: `root-filter-tablebase-audit.json`,
`tablebase-opening165-move83.json` and `storm_diagnostics.json` under `lab/odin`.

An additional four streamed 5-million-node probes locate an earlier conversion
failure: **`50...Ra1`**, putting the rook in front of its own a-pawn. The
reference keeps roughly +4.36 for Black with `...Ra3`, versus 0.00 after
`...Ra1`. `49...Rxa4` still receives about +4.51; by the next decision after
`...Ra1`, the reference is near zero. These are finite-budget estimates, not
tablebase proofs in that larger position, but they make rook placement and
passer support a much sharper training/test target. See
`lab/odin/reference-conversion-confirmed.jsonl`.

The earlier `61...Ke7` in that game is **not established as a blunder**. Its
unrestricted/played reference values were near zero. One attempted restricted
analysis of `61...Kg8` returned a PV outside the restriction; that individual
result is invalid and excluded. Do not use it as a label or a claimed saving
move. This correction is recorded in `code_review_measurement_audit.json`.

## Concrete source defects and the live rules change

The code audit adds three priorities that game narratives alone cannot prove:

1. **Legality-aware SEE.** Two reproduced safe pawn captures are scored -400
   and -200 because SEE counts an illegal king recapture or a pinned bishop.
   Quiescence can prune them. Fix and test legal exchange geometry before
   expanding pruning. These fixtures demonstrate a defect, not its frequency
   or responsibility for a specific site loss.
2. **Draw/TT context.** Static PeSTO is used to delete root choices; internal
   any-repeat detection is not exact threefold; EP canonicalization differs
   from python-chess; TT score identity omits relevant history/rule context.
   Use rule-aware scores and retain good drawing defences.
3. **Current referee semantics.** The live [contract](https://aichessathon.com/docs/agent-contract.md)
   and [official referee](https://github.com/advitrocks9/aichessathon-starter/blob/91f70e54be07e1bf56311962044a08b822c3af50/harness/referee.py)
   now use 600 total plies, opening included, then a draw. Storm still switches
   to material evaluation near played ply 284, collapses its clock forecast
   at 300, and has a 512-entry native history buffer that can overflow on
   longer legal games. Correct all paths, not just a constant.

None of today's ten games, or the forty native games, reaches the old
material-mode threshold. The rule mismatch is a serious successor requirement,
not an explanation for the three observed site losses. Four Storm decisions
in the separate 293-ply supplementary game did enter that obsolete mode.
The historical harness and all archives remain untouched.

## Measurement limits and retained files

The 6,221-position screen and first 34-root pass used aggregated python-chess
UCI info without preserving bound flags. Treat them as exploratory. The final
15-root confirmation retains each score-bearing event's own depth, PV and
bound flags, and uses the last exact event matching final bestmove. All fifteen
played restrictions were verified. The external engine implements ordinary
chess, not the competition's mandatory future intended-move claims or cap
inside every branch. Even a stable score of zero is not a mathematical proof.

The source audit replays every saved FEN/history/PV. The 5-million-node values
above supersede earlier exploratory numbers where they differ. The separate
seven-piece tablebase result provides stronger endgame evidence with its
stated history limitation. The controlled Storm probes clear TT and heuristics
and did not rerun all earlier searches. Their ~63-second Windows warmup is not
a new platform/native Linux initialization measurement.

Main artifacts:

- `lab/odin/site_review.json`: all ten games, clocks, S4 mapping and 44 roots.
- `lab/odin/holdout_review.json`: all forty native games and detailed losses/draws.
- `lab/odin/reference-screen.jsonl`, `reference-deep.jsonl`,
  `reference-confirmed.jsonl`, `reference-conversion-confirmed.jsonl`,
  `reference-summary.json`: offline labels and provenance.
- `lab/odin/Storm-day2-reference-annotated.pgn`: all ten games, original clocks
  and after-position screening evaluations, explicitly marked exploratory.
- `lab/odin/code_review_repro.json`, `code_review_root_filter.json`,
  `code_review_measurement_audit.json`, `storm_diagnostics.json`: code and probe evidence.
- `lab/odin/odin-diagnostics.jsonl`: curated implementation cases, full available
  history, reference provenance and exact SEE fixtures.

The leaderboard snapshot fetched at 16:33 UTC still showed ratings **after
round 24**, although the supplied round-25 game had finished. It placed Samson
52nd at 1752 and AlphaFish first at 2168; all ten opponents were outside that
snapshot's top 25. This is context, not a current rank guarantee or proof about
private rival algorithms. Saved page/metadata: `lab/odin/leaderboard-review.json`.
Source: [public leaderboard](https://aichessathon.com/leaderboard).

The next task is to implement the staged Odin brief, prove its diagnostics,
and test fresh paired games against Storm under the current referee. That
is a concrete route to a stronger contender; rank one remains an outcome
to earn against the field.
