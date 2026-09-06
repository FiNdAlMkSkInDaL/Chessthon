# Tempest r1 against Gladiator — round 39

The user identifies the uploaded agent as Tempest r1; the PGN/log themselves
do not contain its archive hash. Black lost by checkmate after 73 decisions.
All 146 plies from the supplied opening were legally replayed with the current
referee's actual repetition/fifty-move rules. The archived screen includes the
final state as well as every played position.

## Main finding

The early kingside attack was not the decisive, irreversible event. The
reference analysis shows Black recovering and later missing a favourable
continuation. The clearest later mistake is **50...Qg4**, permitting a queen
trade into a bad rook-versus-knight pawn ending. The deeper alternative is
**50...Qg2** (this is not check; an early commentary incorrectly added `+`).

At twelve million reference nodes per search, the unrestricted root chooses
Qg2 at 0.00 from Black's perspective; forcing Qg4 yields -3.85. This supports
a serious transition/long-horizon error. It is a finite reference assessment,
not a tablebase proof of the thirteen-piece root or a measured causal effect
of a particular search feature. The new 3/4-piece tables do not directly solve
this much earlier transition.

| Black decision | Reference alternative | Alternative / played, Black pawns | Budget per search |
|---|---|---:|---:|
| 9...h6 | ...Na6 | -1.01 / -1.62 | 2M |
| 10...hxg5 | ...Nh5 | -1.31 / -1.90 | 2M |
| 18...f6 | ...Rh8 | -2.20 / -2.04 | 2M |
| 31...Ne5 | ...Re8 | +1.92 / +0.43 | 2M |
| 50...Qg4 | ...Qg2 | 0.00 / -3.85 | 12M |

The reversed result for 18...f6 is reference instability, not evidence that
the played move was inferior. Likewise, the earlier broad six-root screen
returned the played move itself as best for some later rook moves, with
different scores in unrestricted and forced searches. Do not count such score
differences as confirmed move errors. Later losses at already -6/-8 positions
are secondary to identifying where a drawable position was surrendered.

## Clock context

Black used 153.4 seconds including increments and ended with 3.1 seconds;
the clock had fallen to 0.899 seconds earlier. The longest decision was
30...Nd7, about 11.5 seconds. Black had about 9.1 seconds when asked for
50...Qg4. The old explanation that we routinely leave 25 seconds unused does
not describe this game. The useful question is whether earlier search work
improved choices enough to justify its cost, and why this later transition
still received a positive engine evaluation.

## Evidence and use

`lab/tempest_edges/round39/round-39-screen.jsonl` records 100k-node full-history
reference probes. `round-39-deep.jsonl` records the initial six forced-root
comparisons. `focused-review.jsonl` holds the additional preselected early
decisions and 12M-node queen-trade comparison, with reference binary and driver
hashes. The 50...Qg4 position is in the candidate diagnostic suite; neither
its reference move nor any lookup response is shipped in an agent.

This game supports testing attack search, position reuse and endgame
evaluation as separate hypotheses. It does not justify adding a literal move
exception, globally avoiding queen trades, or declaring the draw avoidable
solely because a shallow score was positive.
