# Fixed Odin r1: first development loss

This is one selection/development game at **30 seconds + 100 ms**, not a fresh
holdout or the competition's full clock. Fixed Odin r1 (White, ZIP
`460dbab440a3e317680de8a6bb38457ad01b6e3df77194cd34ef10ea1941c1e3`) lost by
checkmate against the minimal Storm rules control
`35c6a33fed2e81acead145de53639ce516b1d24a6701a89a8c5fff81a582baf1` after 128 played
plies. Neither side suffered an operational failure.

## Main conclusion

The first confirmed large deterioration is **32.a4**, followed by a missed
rescue with **33.a5**. The problem appears while both rooks and bishops are
still on the board; the later pawn-race failure is downstream. More search
time may help, but this game does not establish that time alone solves the
decision: Odin spent substantial time and still judged the resulting ending
far too favourably.

| Decision | SF19 reference at 1M nodes per search, White cp | Recorded Odin work |
|---|---|---|
| 11.Kc2 | Ke2 lead −8; Kc2 −70 | depth 10; 967 ms from 30,000 ms |
| 14.Rhe1 | Kd1 lead −9; Rhe1 −87 | depth 11; 2,193 ms from 26,239 ms |
| 19.Bd5 | Nd5 lead 0; Bd5 −72 | depth 11; 707 ms from 19,340 ms |
| **32.a4** | **Rd4 lower bound −43; a4 −243** | depth 9; 434 ms from 4,816 ms; Odin score −68 |
| **33.a5** | **axb5 lower bound −2; a5 upper bound −430** | depth 9; 1,384 ms from 4,482 ms; Odin score −69 |
| 42.Rg2 | Rf7 lead −436; Rg2 −540 | depth 8; 77 ms from 587 ms |

Reference scores are finite-search results, not proven chess values. The two
critical cases were rerun recording UCI bound flags: the best-move rows ended
as lower bounds and 33.a5 as an upper bound. They must not be described as
precise solved scores. The direction of those bounds supports the large gap.
The earlier rows did not retain UCI bound flags and are weaker screening leads.

At move 32, White should keep the rook active (`Rd4`). The played `a4` lets
Black seek `...Bf6`, trade bishops, penetrate with the rook and take e3/h3.
In the actual game, Black instead played `...Rf3`, allowing White to restore
near-equality with `axb5`. Advancing `a5` fixes the queenside pawn structure and
leaves `...Rxh3` and kingside play available. White's later passive rook defence
and inability to restrain the g-pawn follow this strategic concession.

By move 33, Odin had only 4.482 seconds left, but it used 1.384 seconds—about
31% of that bank—and searched 1.83 million nodes. Its score remained −69 cp.
At move 42, the clock was down to 587 ms and depth 8, so later play is heavily
constrained. Native selective depths and node counts cannot be compared
directly with Stockfish's depth or nodes.

## Next diagnostic

Seven exact full-history roots are saved in `fixed-r1-diagnostic-roots.json`.
Prioritize relative plies **42 and 44**, corresponding to moves 32 and 33.
Replay each from its original starting FEN and move list; do not reconstruct
history from its final FEN alone. Compare the performance branch using the
recorded decision budgets, then a controlled larger budget on the same laptop
or signer. A change from a4/a5 to Rd4/axb5 would be encouraging development
evidence; it is not a substitute for fresh paired matches.

No performance-branch result for these exact roots was available when this
review completed. The roots were sent to the branch's owner. This review
therefore does **not** attribute the failure exclusively to evaluation, search
selectivity, TT reuse or clock policy.

## Evidence

- `fixed-r1-game1-screen.jsonl`: all 129 positions, 100k nodes each.
- `fixed-r1-game1-deep.jsonl`: seven selected roots, 1M unrestricted and 1M
  forced played move at each root.
- `fixed-r1-game1-critical-bounds.jsonl`: moves 32/33 repeated with UCI bounds.
- `fixed-r1-game1-source.json` and `.pgn`: exact completed development game.
- `review.py`: reproducible offline SF19 runner; CPU 4 affinity verified for
  both Python controller and engine, one thread, 128 MiB hash, full PGN history.

Stockfish executable SHA-256:
`3b5881df3d6f92817cf6664a6a18a473b50d424c71a1247fe4268090db281413`.
The reference workload took about 57 seconds total. All subprocesses exited;
the VPS and submission source were untouched.
