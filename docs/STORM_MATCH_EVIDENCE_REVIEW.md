# Independent review of Storm r2 match evidence

Reviewed `linux_match.py`, `paired_match_stats.py`, `summarize_match.py`, the completed eight-game `screen-r2.jsonl`, and the saved initial full-clock holdout lane records. Read-only review of active code; no engines or native workloads were started.

## Final native holdout result

The completed audit in `lab/storm/holdout-r2-audit.json` **passes** with no failure reasons. Both final run summaries are present and valid. All 40 games, comprising 5,028 played plies, replay legally against every logged request FEN and UCI. The 20 complete colour pairs cover exactly the predeclared opening indices 160–179; there are no excluded failure pairs. Both agents' ZIP identities and all recorded source identities agree throughout. There are no protocol, extraction, envelope or cleanup failures.

Storm r2 recorded **31 wins, 4 draws and 5 losses** against v3: 33 points from 40 games, a score of **82.5%**. Its outright win rate was 77.5%. The existing paired percentile bootstrap, with 20,000 resamples, seed 20260904 and 95% confidence, gives a score interval of **71.25%–92.5%** and standard error 0.05374871787715033. The lower bound exceeds the required 50%, and all 20 required pairs are included. Pair-total buckets for 0, 0.5, 1, 1.5 and 2 points contain 0, 1, 4, 3 and 12 pairs respectively.

The analyzer's logistic conversion gives a relative Elo estimate of +269.366, with interval +157.659 to +436.432. That is a description of this fixed local matchup and opening sample, not a tournament rating or a prediction against the public leaders. The short-clock screen and supplementary site-opening games were not included in this calculation. The site-opening coverage limitation below remains relevant despite the clear improvement over v3.

Lane A completed 20 games/10 pairs on CPU 1; lane B completed 20 games/10 pairs on CPU 0. Both used the unchanged official referee and runner with 120,000 ms + 500 ms, the 90-second import budget, Python 3.12 on native Linux x86_64, and the checked resource limits. All 80 agent service identities were fresh and distinct. The largest positive/negative consecutive-clock residuals were approximately +1.056/-0.940 ms, consistent with the documented integer-clock approximation.

The completed evidence files have these SHA-256 identities:

| File | SHA-256 |
|---|---|
| `holdout-r2-lane-a.jsonl` | `70dc3565814b4315516c2f3f53bb7e98f01259dd719eed4375c8c9671163b135` |
| `holdout-r2-lane-b.jsonl` | `700d6cf94fa51dd26d5821ccc8bf6f5c5cccfaefc10b378f834877b5545aa5b1` |
| Candidate r2 ZIP | `15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c` |
| Baseline v3 ZIP | `3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408` |
| `lab/openings.fen` | `9b7d75f13d4b376743ac2fe000b9665147b582beb6dc541e5f91453a7192f0eb` |

Recorded source hashes were compared with the unchanged audited workspace bytes:

| Source | SHA-256 |
|---|---|
| `harness/referee.py` | `0a05b3cf959123110a1d2bfec78354bb6bd5e1660810fbb5baa3fc46ccb5e732` |
| `harness/rules.py` | `4fbaa1ac5010066287055bdd847c59a1d57341cdd721728891307d5761f702da` |
| `harness/runner.py` | `31e6478905576d56e22b675217fd582dce554fbaf3850afc55d8aab2b3f55f4e` |
| `harness/sandbox.py` | `2124822815728cbab7c9b1b61f3bff23fbb1ab340658d2ba58c7c2d99bff1f2c` |
| `lab/storm/linux_match.py` | `0b20a9a6e67e03c6d98fff05334adb8ec6a4ba4d971d16e3dc7b86e518165e6f` |
| `lab/laptop_match.py` | `bdaa949ee65c13cd586bfc17537818fdb3e389e3acf40b8a694e35217b58f7e8` |
| `lab/laptop_runner.py` | `57f3c62d7a5070436ebbb056c65e7394d292b692309a263139298767a5e7c61e` |
| `lab/release_audit.py` | `ecfd901d3868dc6e293172051aa83d64fe658486e40f1b16b31cf4d0e8b838c2` |
| `lab/paired_match_stats.py` | `8ce432d0d23404af5d8b0c5785bc2fca8f976e8fc601b38c5828672b90e257ef` |

The same audit command documented below now returns exit code 0. Engine source, native runner, analyzer and archives were unchanged during this final review.

## Findings

**No observed scoring or provenance error invalidates the completed screen.** All eight PGNs replay exactly against the logged per-move FENs and returned UCIs. The candidate won all eight games by checkmate. There are four complete colour pairs, no duplicate/mismatched identities, no protocol failures, and no envelope, cleanup or extraction-integrity errors. Each game identity agrees with its immutable ZIP manifest. Recorded harness/helper source hashes agree with the workspace files.

The baseline SHA-256 is `3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408`, exactly matching Desktop `v3-agent.zip` and `dist/agent-v3-linux-x86.zip`. The baseline desktop file was called `agent.zip` during these tests; it was renamed at the user's request on 5 September. The candidate SHA-256 is `15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c`, matching `dist/storm-r2-linux-x86.zip` and the current Desktop `agent.zip`.

**The full-clock promotion calculation must use only the two holdout logs.** The screen uses 10,000 ms + 100 ms; both holdout lanes use 120,000 ms + 500 ms. `paired_match_stats.py` deliberately reads game rows, not `run_start` metadata, so it would silently accept pooling these time controls because their ZIP hashes agree. It also does not independently reject an envelope/extraction/run error recorded outside the fields it understands. The final review must check those metadata/integrity fields and completion separately before applying its statistical gate. This is a limitation of the analyzer's scope, not an observed problem in the existing data.

The holdout plans are disjoint: lane A covers indices 160–169 and lane B 170–179, two colours each. Their runtime and source hashes match. Require both final `run_summary` records, all 40 planned games, and all 20 complete pairs before drawing the predeclared holdout conclusion. Intermediate results and the four-pair screen should remain descriptive.

**The clock summaries are sufficiently accurate for these completed legal games.** `summarize_match.py` estimates each final clock using the last incoming integer clock minus measured call duration plus increment. Comparing consecutive requests gives residuals between approximately -0.93 and +1.04 ms, consistent with integer truncation and wrapper overhead. It is not an exact referee-clock export, but this error cannot explain seconds of allocation differences. In a future flag/crash/illegal game, its unconditional increment and inclusion of the failed request would be wrong; use only successful legal games for the reported final-clock averages. None of the completed screen games has that issue.

`mean_completed_depth` summarizes only available S4 telemetry. V3 has no comparable telemetry, and Storm's forced/panic branches may omit it. Do not present this field as a matched depth improvement or as an average over every move.

## Site-opening coverage

The local corpus is materially different from the actual site positions, despite similar piece counts and PeSTO material phase:

| Feature | All 200 synthetic starts | Holdout 160–179 | 14 unique actual site starts |
|---|---:|---:|---:|
| Mean minor pieces off their own back rank | 1.52 | 1.40 | 4.21 |
| Starts with a castled king on c/g home rank | 0 | 0 | 4 |
| Starts in check | 29 | 7 | 0 |
| Mean FEN fullmove number | 5.64 | 5.50 | 6.79 |
| Mean remaining pieces | 30.91 | 31.30 | 30.86 |

The synthetic generator emphasizes early captures, checks and central squares while choosing among four moves by its custom score; it does not reproduce a standard opening repertoire. Consequently, the full holdout is useful relative-strength evidence on its declared corpus, but is not sufficient by itself to claim that the gain transfers unchanged to the tournament's curated starts.

**A small supplementary site-opening check is materially useful.** Prefer two full-clock colour pairs from `site_openings.fen` indices 8 and 10: the former is the observed Two Knights Defence position with both kings castled; the latter is the later, heavily developed King's Indian Classical position. These directly exercise coverage missing from the synthetic starts. An operationally convenient alternative is the contiguous slice 8–10, three pairs. Declare these as supplementary stress checks using already observed positions, keep their results separate, and do not add them to the holdout confidence interval or replace unfavorable holdout pairs with them.

Counts above were calculated directly with python-chess from the FEN files. Fourteen unique site positions cover all 15 exports because rounds 4 and 10 share an opening. No source or workload was changed during this review.

## Reproducible final holdout audit

Run from the repository root with Python 3.12 and the lab dependencies:

```powershell
python -m lab.storm.test_validate_holdout
python -m lab.storm.validate_holdout lab/storm/holdout-r2-lane-a.jsonl lab/storm/holdout-r2-lane-b.jsonl --out lab/storm/holdout-r2-audit.json
```

The validator accepts exactly two logs and returns exit code 0 only when both evidence integrity and the existing paired statistical gate pass. It requires all 40 games and both final summaries, the complete disjoint colour pairs at indices 160–179, the frozen r2/v3 ZIP hashes, 120,000 ms + 500 ms with a 90-second import budget, consistent source/package identities, and no extraction, service-envelope, cleanup or protocol failures. It legally replays every PGN, checks every logged request FEN and UCI against that replay, verifies termination and candidate scores, and then calls `paired_match_stats.analyze_rows` with at least 20 pairs and a lower confidence bound strictly above 0.5. The JSON keeps the evidence verdict and statistical result separately visible and does not embed host-specific paths.

Eight small tests cover metadata acceptance, rejection of the short-clock screen, mismatched archive identity, incomplete runs, a valid complete 50% result that must fail promotion, PGN/request disagreement, recorded cleanup failure, and concurrent lanes assigned to the same CPU. The saved partial-log audit replayed six games and 659 plies without integrity mismatches; it correctly failed because the remaining games and final summaries were absent. This partial check is a validator check, not a promotion result.
