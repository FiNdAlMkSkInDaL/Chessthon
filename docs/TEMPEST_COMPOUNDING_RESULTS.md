# Tempest compounding experiments — completed 6 September 2026

**Desktop `agent.zip` remains Tempest r1.** Six complete development screens
produced 96 games and 13,287 legally replayed plies. No tested search addition
or bundle reached the predeclared 60% nomination threshold. The fresh
confirmation families were not consumed, and no 112-game run was launched.

There is a reusable new component: a Linux-packed, native/protocol-tested
three/four-piece tablebase candidate. It has not demonstrated a general
playing-strength improvement and is not promoted.

## Complete game results

All screens used eight previously used opening families, reversed colours,
500 ms search allowance and audited state restoration. Linux workers occupied
separate pinned cores; two additional screens used separate laptop cores.
These are development games, not the competition's 120+0.5 game clocks.

| Candidate | Control | Platform | W/D/L | Score | Decision |
|---|---|---|---:|---:|---|
| Queen-dependent pawn depth protection | Narrower search with lazy predicate | Linux | 3/8/5 | 43.75% | Reject |
| Preserve one ply instead of full exemption | Same narrower control | Linux | 1/9/6 | 34.375% | Reject |
| Original online capture history | Same narrower control | ARM | 5/8/3 | 56.25% | Inconclusive |
| Equal-memory two-slot search cache | Same narrower control | ARM | 5/5/6 | 46.875% | Reject |
| Narrower search + capture history + tables | Released Tempest r1 | Linux | 3/7/6 | 40.625% | Reject |
| Tables alone, with clock guard | Released Tempest r1 | Linux | 4/8/4 | 50% | Inconclusive |

Every game was retained. All source/helper/reset/legal replay audits pass.
Do not pool these wins or infer a combined Elo: controls, platforms and
candidates differ. The bundle result rejects that bundle; this is not a
complete factorial design proving that tablebases caused a negative interaction.

The table-only arm reached the new four-piece route just three times in two
games, so its overall score is particularly weak evidence about table coverage.
Across both relevant screens, all 90 observed four-piece table decisions
preserved the best available rule-adjusted child result under replayed history.
Of those decisions, 47 were already losing, 41 drawn and two winning.

## Implemented changes and gates

The queen and graded alternatives preserve the existing check, hash, killer
and advanced-pawn safeguards. Source-derived predicate boundary comparisons
cover both colours, queen presence, square geometry and reduction magnitudes;
native searches, perft and ABA resets pass. Neither alternative is retained
as an improvement over the original narrow exemption.

Capture history uses 72 additional rows in the existing mutable history buffer:
moving piece, victim type and destination. Bounded gravity rewards actual
capture cutoffs and penalizes previously searched captures. Pruned moves are
not recorded as failures. The history breaks equal static capture ranks only;
hash priority and promotion ordering remain intact. It learned nonzero values
and changed root capture order on five of 18 diagnostic roots. Its initial
positive screen did not turn into a successful bundle against the release.

TT store instrumentation preserved exact fixed-node search results. At four
million nodes it counted 952–1,231 collisions per root destroying deeper
current-generation entries of depth at least six. That met the predeclared
implementation gate for an original two-slot bucket with unchanged total
entry count. The bucket passed 105 native key/collision/age/bound/mate checks
and perft, but lost its playing screen. It is not retained in the candidate.

## Exact endgame component

The current [competition rules](https://aichessathon.com/docs/rules.md), fetched
again during this work, explicitly permit shipped tablebases and include
`chess.syzygy` in the base image. The [Lichess mirror](https://tablebase.lichess.ovh/tables/standard/)
provided all 70 three/four-piece WDL and non-rounded DTZ files. Their
4,877,792 bytes were verified against the published SHA256 manifests, including
the separate non-rounded manifest. Initial obsolete/mismatched download URLs
and their errors are retained in the inventory; HTTPS verification was not disabled.

The move-selection policy is original code using the preinstalled probing
library. It retains our existing KQK/KRK mate-distance policy and expands
coverage to pawn endings, bishop-and-knight mate and other four-piece material.
It considers actual fifty-move counters, immediate known repetitions,
opponent repetition replies and mate precedence. It avoids stalemating queen
promotion in the tested KPK position by promoting to a rook.

This is root coverage, not table probing inside the native search. Castling
and the final 200 absolute plies use the existing search for the new coverage.
Below 1,200 ms remaining, the broader Python probe is declined while the old
three-piece DTM remains available. There is no claim of a complete
history-expanded or 600-ply tablebase proof. The distinction between WDL's
reset-clock assumption and DTZ is documented by
[python-chess](https://python-chess.readthedocs.io/en/latest/syzygy.html).

Validation includes 792 random nonterminal positions across all 33 applicable
material families, colour mirrors and halfmove-99 boundaries; the two remaining
families are automatically insufficient material. There were 4,983 root checks,
including 64 complete winning conversions over 2,606 plies. All passed. The
largest local measured policy call was 281.4 ms, motivating the clock guard.
Actual agent tests exercised both sides of the guard and panic operation.

The table-only archive is preserved at:

`lab/tempest_edges/native/tables_guard/candidate-linux-x86.zip`

SHA256:
`6282db3d2f8add9fb9c5636c0b6f3117e05aa6b89400cba9d5ae0fa341b4e2c1`

It contains 85 files and 5,295,632 uncompressed bytes. It was packed on Linux
x86_64 Python 3.12 and passed the one-core/2-GiB/no-swap native and unchanged
official-runner protocol gate using referee commit `284724ab...`. The official
runner's cold agent import was 33.667 seconds. Its KPK table-route probe took
5.57 ms and its KBNK probe 9.23 ms. The gate also checks native readiness,
perft, deadlines, long histories, and mate/cap handling.

The initial gate launcher failed before importing an agent because direct
script execution did not put the validation root on `sys.path`. Module
execution fixed the launcher; the same packed archive passed the second
attempt. Both attempts are retained. This is operational readiness evidence,
not full-clock strength confirmation. No Desktop archive was replaced.

## New loss and the next useful research direction

See `TEMPEST_ROUND39_REVIEW.md`. The strongest identified error is 50...Qg4
against Gladiator, exchanging queens into a bad rook-versus-knight pawn ending.
At 12M reference nodes, ...Qg2 holds an approximately equal evaluation, while
the forced played move evaluates to -3.85 for Black. At 1M/4M/12M nodes our
exploratory bundle still chooses Qg4; at 12M it scores it +0.92. These are
full-history but cold-TT diagnostics, not a replay of the site's exact prior TT.

The R37 improvement is also unstable: the bundle chooses Qc2 at 1M but returns
to Qxa5 at 4M and 12M. More selective depth alone has not solved these cases.

The next distinct hypothesis should address **endgame transition evaluation**:
king access to pawn fronts, blockades, rook activity and rook-versus-minor
imbalances. Collect a broader, family-separated development corpus of such
positions with stronger labels and forced-alternative comparisons; fit a small
original phase-dependent correction against the current evaluator. Validate
its actual native search decisions and tail regressions, not only average
prediction error. Do not hardcode Qg2, globally avoid queen trades, or tune only
on the latest loss. Four-piece tables cannot directly repair a thirteen-piece
transition several moves earlier.

## Reproduction

`lab/tempest_edges/results.json` aggregates the six source-bound replay audits.
The lab README maps every generator, frozen source, probe, match, table hash and
native artifact. `completion-manifest.json` binds final evidence and unchanged
release identity. Failed and inconclusive experiments remain available; no
candidate has been relabelled as a winner.
