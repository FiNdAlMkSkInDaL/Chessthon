# Native holdout opening 165: completed Storm loss

This is a descriptive review of one completed game while the fixed holdout continues. It does not change the engine, opening selection, stopping rule or promotion gate. No chess engine analysis or tuning was run. A legal replay can establish what happened; it cannot certify a forced win, a best move or the first losing decision.

## Identity and reproducibility

Source: `lab/storm/holdout-r2-lane-a.jsonl`, run `20260904T225631Z-b66b297d`, game 12, pair 6, opening index 165. Storm r2 was Black and lost by checkmate after 205 plies from the supplied opening FEN. The other completed colour leg in this pair was a threefold-repetition draw.

- Candidate ZIP SHA-256: `15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c`.
- V3 ZIP SHA-256: `3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408`.
- Exact source game JSON line SHA-256, excluding its line ending: `683a9909afd85afed3c17d3da0dc5a1f8e40d5647083aaf3a91557229bdede20`.
- PGN string SHA-256, UTF-8 without an added line ending: `acdfaea0d3ba966f62ca39c18231ae37ad5533b84a77a449573ec6916f49949b`.

The frozen copy of the completed game row is `lab/storm/r2-loss-165.game.json`; the PGN is `lab/storm/r2-loss-165.pgn`; the full move-by-move clock, material, FEN and telemetry trace is `lab/storm/r2-loss-165.analysis.json`. Regenerate with:

```powershell
python -m lab.storm.inspect_game lab/storm/holdout-r2-lane-a.jsonl --game 12 --out-prefix lab/storm/r2-loss-165
```

The inspector runs the existing native-game integrity validator first. Every logged request FEN and returned UCI agrees with the legal PGN replay and final referee result. Its output contains no host-specific paths. Move numbers below are the PGN's FEN fullmove numbers, starting at 6; they are not move counts from the start of the match.

## Material and king sequence

Both sides castled on move 11. This was a long rook-ending loss, rather than an early attack on an uncastled king. After `48...Qxe5+ 49.dxe5 Rxa4`, Storm had a rook and four pawns against a rook and three. Its pawns were a5, f7, g6 and h6; White's were e5, f2 and h3.

Storm advanced `51...a4`, `54...a3`, `55...a2`. The a-pawn then remained on a2 until White captured it on move 80. Black's own rook occupied a1 in front of it, while White could keep the rook active on the a-file and the king near the central pawns. Black's king travelled from g8 through f8/e7/d7/c7/b6/c5 to c4 on move 66, then back through d5/c6/b7/c7 to b8 on move 71. White's king stayed on f4 during this stretch. The presence of an extra pawn and an advanced passer did not by itself make conversion straightforward.

`72...g5+ 73.hxg5 h4` created White's passed g-pawn and Black's passed h-pawn. `74.e6 fxe6 75.g6 e5+` added a black e-passer while White's king became active on f5/f6. After `79...Rf1 80.Rxa2 Rxf3+`, the a-pawn was gone: each side had a rook, White had g6, and Black had e4 and h3.

The visible material loss is `88...Rxg7 89.Ra7+`: White's rook checks the black king on c7 with the rook on g7 behind it. After `89...Kd6 90.Rxg7`, White had a rook against Black's two pawns. `90...e3 91.Rg1 h2 92.Rh1 e2` did not promote: White's king captured e2 on move 95 and the rook captured h2 on move 96. The remaining king-and-rook ending finished with `106.Rh4+ Kg8 107.Rh1 Kf8 108.Rh8#`. This identifies the played skewer and liquidation; it does not establish that Black could still save the game on move 88.

## Clock and recorded search estimates

Storm spent 62.983 seconds on its first 20 decisions, against V3's 71.133 seconds. Over the whole game, Storm spent approximately 166.763 seconds across 102 decisions, including time replenished by increment. Its estimated final reserve was 4.232 seconds; V3's was 8.545 seconds. Reserves are calculated from the final incoming integer clock minus wrapper call duration plus the 500 ms increment, so they are millisecond approximations.

| Storm move | Clock before, s | Call duration, s | Reported completed depth | Reported score, cp |
|---|---:|---:|---:|---:|
| 47...g6 | 31.317 | 5.549 | 20 | +198 |
| 49...Rxa4 | 25.168 | 1.183 | 20 | +200 |
| 52...Kg8 | 19.816 | 7.143 | 20 | +247 |
| 55...a2 | 12.374 | 1.628 | 17 | +210 |
| 66...Kc4 | 7.399 | 0.832 | 20 | +256 |
| 69...Kb7 | 6.321 | 0.568 | 15 | +164 |
| 77...Kc8 | 3.826 | 0.826 | 15 | 0 |
| 83...Rf4 | 4.110 | 1.174 | 16 | -125 |
| 86...Rg4 | 2.737 | 0.577 | 18 | -469 |
| 89...Kd6 | 2.710 | 0.876 | 18 | -500 |

These are Storm's own completed-search scores, from Black's perspective, not an independent evaluation. They stayed near +255/+256 from moves 56–68, declined through +164/+115/+67 at moves 69–71, were zero at moves 77–82, and became negative from move 83. V3 has no equivalent telemetry, so these depths cannot establish a depth advantage over the opponent.

The longest Storm call was `52...Kg8`: 7.143 seconds from a 19.816-second clock. Its recorded dynamic target was 1.441 seconds; that target is a soft allocation, not the hard deadline. This request returned legally with roughly 13.173 seconds left after increment. By the time the pawn race developed, Storm was operating with a few seconds plus increment. This example therefore does not support the explanation that it lost while leaving a large time bank unused. It supports retaining this long rook ending as a diagnostic for conversion and late-game allocation; it does not show that a particular alternative allocation would have saved it.

## Operational checks and limits

There were no protocol, extraction, service-envelope or cleanup failures. Storm imported in 30.079 seconds, V3 in 25.622 seconds, both below the 90-second budget. Their cgroup peak memory was 433,729,536 and 414,531,584 bytes respectively, below 2 GiB. Both services were recorded on CPU 1 with the expected one-core quota and restrictions. All 205 played plies replayed successfully and the official claim-draw/cap conditions did not terminate the game earlier.

There are 98 S4 telemetry records for 102 Storm decisions. The entrypoint deliberately omits these records when a filtered root has one move, or for another direct-return branch; absence alone is not an operational failure. For example, `61...Ke7` returned in about one millisecond with an 8.552-second clock, while its other legal king move would revisit a prior position. No failed request or clock flag is recorded.

The strongest conclusion from this game is narrow: Storm can establish a favourable self-evaluation and an extra pawn, then fail to convert a complex rook ending under a depleted clock. This is a concrete retained weakness, alongside the full holdout's aggregate evidence. No best-move labels, evaluation ground truth or causal pruning diagnosis are supplied here.
