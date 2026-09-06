# Odin checks against the five final-day games

Rounds26–29 add three Storm wins and one draw: ChessML, JSP and NeuralGambit
were beaten; FuzzyBot was drawn after377 played plies. The subsequently supplied
round30 is a loss to Team1. Storm finishes day two with **9 wins,2 draws and
4 losses in15 games**:10/15 points. The wins still contain useful mistakes to test.

The positional candidate and its24-feature coefficients were fixed before
these games arrived. Its final112-game release plan is frozen separately.
None of the904 reconstructed positions matches a final-holdout position.
These selected diagnostics cannot establish an unbiased win rate and are not
included in the release score.

## What the exact release source does

All20 selected positions were reconstructed from the full PGNs. Each was
tested twice with `odin_submission/`: once through the real `get_move` clock
controller using Storm's recorded remaining clock, once with a3-second root
budget. The agent's historical observations were reconstructed only from its
own served turns and legal own moves; future positions were never supplied.
The TT was cleared per case. All40 responses were legal, source hashes stayed
unchanged, and the native root needed no additional specialization.

These probes ran on Windows ARM, where search speed is lower than the Linux
signer. The historical game's TT is unavailable. A different completed depth
can change a move. The actual Linux full-game comparison remains the release
test of playing strength.

The table reports same-root, cleared-hash,2-million-node Stockfish19 reference
searches, in pawns from Storm's side. Positive favors us. Each proposed move
was searched separately. These are finite analyses, not mathematical values;
small differences should not be overinterpreted.

| Game and turn | Storm played | Odin at recorded clock | Reference finding |
|---|---|---|---|
| ChessML21... | Nc6 | a6 | Partial improvement: approximately−1.82 to−1.30; Rc7 was the reference preference at−0.37. |
| ChessML29... | a6 | Rxg5 | Better defense: approximately−4.27 to−2.99. The3-second probe still played a6; the adaptive probe spent6.65s and found Rxg5. |
| ChessML75... | Rg5+ | c1=Q | Odin promotes immediately and the reference finds a forced mate. Storm's move remained overwhelmingly winning. |
| JSP24... | h6 | Re8 | Only a small improvement; Bxd5 remained the stronger reference choice. |
| JSP32... | Rb2 | Qd8 | A regression in this probe: approximately+2.05 to+0.95. Bxd5 was preferred at+2.46. |
| NeuralGambit26. | Rc1 | Ne5 | Clear recovery: approximately−0.05 to+4.96; both Odin budgets find Ne5. |
| NeuralGambit46. | Qf4+ | Qh4+ | Partial improvement: approximately+3.17 to+4.85. Qxg2 was preferred at+7.55. |
| FuzzyBot18... | Nxe4 | Nb4 | Smaller improvement: approximately−1.13 to−0.73. |
| FuzzyBot43... | Rc4 | Rc4 | Still unresolved. Nf5 was preferred at+3.45, while Rc4 was approximately+1.25. Both Odin budgets repeat Rc4. |

The shallow screen produced false alarms too. NeuralGambit57.a7 was its
largest apparent loss, but the deeper same-root analysis preferred a7 at
about+8.5. FuzzyBot39...Bxa1 was also vindicated. JSP45...Rg1+ retains a
forced mate. Those moves should not become "mistake" regression fixtures.

The tactical point of NeuralGambit26.Ne5 is that the knight attacks the queen
on g4 with tempo. The reference continuation26...Bxe5 27.dxe5 Qh5 28.Bc1
disrupts Black's coordinated attack. Storm's26.Rc1 spends that tempo on a rook
move and permits...Rf6, bringing the other rook toward the exposed king.

In FuzzyBot43...Nf5, Black's advanced c2-pawn is the central asset. The
reference line uses...Rd8 and...Rd1+ to invade the first rank, followed by
knight activity and promotion threats. Storm's...Rc4 allows Rf1+ and gives
White time to coordinate a blockade. Odin's repeated...Rc4 is a failure to
recognize the stronger conversion plan, not an operational or clock failure.

The JSP regression is also concrete:32...Bxd5 removes the central knight;
after exd5,...e4 attacks the queen on f3, gaining time before...Qxd5. Odin's
Qd8 misses that forcing sequence in the recorded-clock probe. These short
plans are reference continuations, not forced proof of the eventual result.

## The long FuzzyBot draw

At absolute plies289,301 and389, Odin returns legal moves and never switches
to Storm's obsolete300-ply material-adjudication mode. The reference is near
zero at these late positions. At ply389 the fifty-move clock makes the draw
immediate after a quiet move; Odin recognizes it and returns in about19ms.
The late draw is therefore not evidence that extra thinking could recover a
win at that point. The earlier43...Nf5 opportunity is the more useful target.

Odin still gives a roughly+2.8 internal score to one near-drawn rook-versus-
bishop position at ply301. Removing the obsolete cap does not by itself solve
evaluation of low-material draws. This remains a concrete future evaluation
and search diagnostic, alongside JSP32... and FuzzyBot43.... No change to the
frozen release is justified by these selected positions alone.

## Final round30: Team1

The loss turns on two decisions while Storm still has substantial time,
rather than on its later near-empty clock. The reference's same-root2M-node
comparison rates25.Qg3 around−2.97 for White, against25.Qf4 around−0.32.
After Qg3 Qxg3 hxg3, White retains the vulnerable e3-pawn and inherits doubled
g-pawns; the resulting position favors Black's central pawns and active knight.
The alternative Qf4 Qxf4 exf4 removes the e3 target and opens the e-file.

At the exact move25 position with70.696s remaining, Odin's adaptive controller
spends4.52s and chooses **axb5**, rated around−0.51 by the same reference.
This is a substantial recovery. Its independent3-second probe instead chooses
Rf1, rated−2.58. The useful extra thinking in the adaptive probe is evidence
from one position, not a general measured time-management gain over Storm.

At29.Kf2, Storm has59.881s remaining. Moving the king onto f2 permits...Ng4+
and further tempo gains against the exposed king. The reference rates Kf2
around−4.72 and prefers29.Rd2 around−1.98: already difficult, but more resistant.
**Odin repeats Kf2** in both budgets, reaching depth14 in the adaptive Windows
probe. This remains an important unresolved king-safety/endgame-transition
diagnostic. An exact-source Linux rerun was queued, then cancelled when the
user prioritized an immediate expedited release. These root results remain
Windows diagnostics, and must not be described as completed Linux reruns.

The three other pre-loss screen candidates—9.Nxf4,16.Rad1 and21.Qxd3—are
vindicated by deeper analysis; none shows a meaningful same-root loss. The
initial unfiltered selection included already hopeless late positions. That
selection was preserved separately, then replaced **before querying Odin** by
five spaced positions whose screen score before the move was at least−3.5.
This makes the selection useful for locating the loss, without claiming it is
an unbiased sample. Round30 has127 reconstructed positions and no exact-position
overlap with the frozen holdout.

## Reproducible evidence

`lab/odin/new_games/` contains all five streamed screens, source PGN hashes,
the20 roots selected before Odin answers,40 actual-source probes, separate
unrestricted/forced-move reference searches, and `review-summary.json`.
`probe_odin.py` records the complete source-file identities. Reference scores
come only from completed iterations without bound flags. Short mate and
immediate-draw searches may reach the reference engine's maximum depth before
the node ceiling; the actual node count is retained. No reference engine,
position answers, labels or game files are included in Odin's submission ZIP.
