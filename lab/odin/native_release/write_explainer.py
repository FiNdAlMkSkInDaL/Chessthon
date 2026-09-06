"""Generate the judge-readable evaluation provenance from the frozen fit result."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
fitpath=ROOT/'lab/odin/quiet_eval/expanded-result.json'
fit=json.loads(fitpath.read_text())
table='\n'.join(f'| {name} | {mg} | {eg} |' for name,mg,eg in zip(fit['features'],fit['mg'],fit['eg']))
document=f'''# Odin v5 — engine and evaluation explanation

Prepared source: `odin_submission/`. Its release status is tracked separately
in `ODIN_RELEASE_PROGRESS.md`; this explanation is not a promotion decision.

Odin is an original Python/Numba classical chess engine. It uses bitboards,
incremental PeSTO piece-square/material accumulators, iterative deepening,
alpha-beta/PVS, a transposition table, check-aware quiescence, legal static
exchange evaluation, selective pruning, late-move reductions with re-search,
and an adaptive wall-clock controller. python-chess provides the FEN/UCI legal
root boundary. The agent starts a new process each game and warms its actual
native search signature during import. It creates no extra worker threads and
makes no network requests.

## Positional evaluation

The base is Ronald Friederich's published PeSTO tables, retained with their
original values and phase interpolation. Odin adds24 signed geometric features
computed directly from the current board. They are counts and distances, not
stored answers for particular positions. Every feature is White minus Black.

The phase is capped at24 and counts knights/bishops as1, rooks as2 and queens
as4 for both sides. The correction is the nearest integer to
`(MG * phase + EG * (24 - phase)) / 24`, clipped to[-400,+400] cp.
Here `MG` and `EG` are the dot products of the features and the columns below.
The correction changes sign for Black to move. The base includes the existing
10cp side-to-move tempo. The legal Python fallback retains the PeSTO base.

| Feature | Middlegame cp/unit | Endgame cp/unit |
|---|---:|---:|
{table}

Isolated pawns have no friendly pawn on either neighboring file. Doubled pawns
count the extras beyond the first pawn on a file. Supported pawns are attacked
by another friendly pawn. Passed pawns have no enemy pawn ahead on their own
or either neighboring file; their advancement counts ranks from the starting
edge. Blocked passers have an occupied next square. King distances are
Chebyshev distances to passed pawns. The additional quadratic passer feature
is `max(0, advancement - 2)^2`.

Open rook files contain no pawns; semi-open files contain enemy pawns but no
friendly pawn. Shelter counts at most one friendly pawn in the first two
forward ranks on each of the king's three nearby files. King-file openness
means neither side has a pawn on that file. Bishop pair means at least two
bishops. Rook seventh means the opponent's second rank.

Mobility counts attacked squares excluding friendly occupancy and enemy pawn
attacks. King pressure counts attacks into the enemy king's square and ring,
with knight/bishop weights2, rook3 and queen5. This is multiplied by the number
of participating attackers, capped at3, and is active when the attacking side
has a queen. The final five terms are simple material counts. Feature extraction
was checked against independently written python-chess geometry on11,202
positions including color mirrors.

## Original offline fitting

The fixed data selection drew6,000 stratified rows from the earlier private
20,000-position corpus, preserving its opening-family train/validation split.
Four one-thread local Stockfish19 processes supplied100,000-node references.
Forcing PV prefixes were advanced to quiet leaves, within a fixed two-analysis
and12-ply bound. Accepted rows required a completed exact search iteration,
stable last-two-iteration scores within40cp, no mate or score beyond1000cp,
and a quiet recommended move. 5,668 rows passed. Canonical-position
deduplication left4,247 training and1,354 validation rows with no cross-split
position overlap.

The fit uses Huber100 regression with bounded coefficients and ridge
regularization. Original training families alone select ridge100 from
10/100/1000/10000, using a deterministic internal20% family holdout. The final
coefficients are refitted on all training rows and rounded to integers.
The expanded feature experiment reused a validation partition already examined
for an earlier experiment, so its error figures are descriptive. Playing
strength must be established separately on the frozen game holdout.

Fit result SHA-256: `{hashlib.sha256(fitpath.read_bytes()).hexdigest()}`.
Full selection, label, fit-plan and reference hashes are retained under
`lab/odin/quiet_eval/`. The release ZIP contains readable Python source and
the original small coefficient arrays. It contains no Stockfish code, binary,
published chess network, training corpus, position-answer lookup or runtime
training dependency. This follows the competition's [training and source
rules](https://aichessathon.com/docs/rules.md).

## Referee and release validation

The current600-ply limit counts the opening's absolute FEN plies and ends in
a draw; ordinary terminal outcomes take precedence. History storage expands
with the actual game. En-passant hashing includes the EP field only when a
capture is legal. SEE excludes pinned and illegal king recaptures. Every
legal root move remains available, including quiet defenses and drawing moves.

The fast search uses a repeated-position draw heuristic and position-keyed
transposition reuse. These are selective-search approximations. The unchanged
official referee determines actual automatic threefold/fifty-move outcomes.
No claim of exact full-history search is made for this release lineage.

Final tests use a separate unchanged official harness snapshot, commit
`91f70e54be07e1bf56311962044a08b822c3af50`, and the published Python3.12
package versions. The signer enforces one CPU per active player,2GiB,
single-thread libraries and no network socket creation. Its EPYC-Genoa CPU
differs from the competition's EPYC9V74; this limits hardware equivalence.
The source is read-only, with no full read-only root mount or aggregate/tmp
quota. These limitations are recorded in the native evidence.

The user replaced the planned80+32 confidence gate with an expedited practical
decision after16 full-clock games. Odin scored9W/2D/5L (62.5%) against minimally
rules-corrected Storm, with zero operational failures; every game passed legal
replay, clock, source and resource checks. The native correctness/runtime gates
also passed. This does not establish a precise win rate or satisfy the cancelled
95% confidence criterion. The separate original-Storm32-game guard was not run.
Desktop `agent.zip` is the exact tested Linux ZIP; Storm and v3 are preserved.
The complete decision and evidence are in the expedited release report.
'''
(ROOT/'docs/ODIN_AGENT_EXPLAINER.md').write_text(document,encoding='utf-8')
print('Wrote docs/ODIN_AGENT_EXPLAINER.md')
