# Site logs

These are the platform games I had exported into the repo. The logs do not embed an archive hash, and none of this is a leaderboard rank. The raw logs are not kept at the repository root. Scores below are the log results. The lessons are only what the reviews already in `docs/` concluded.

## Day 1, rounds 1–15

Fifteen games. [`STORM_GAME_FORENSICS.md`](STORM_GAME_FORENSICS.md) treats them as the deployed v1, not Storm v4.

8 wins, 2 draws, 5 losses. All five losses were legal checkmates. Both draws were automatic threefold claims. 1,712 plies replayed legally. Mean clock left was 33.535 seconds, median 29.521. The first 20 decisions averaged 58.557 seconds, with a standard deviation of 0.882.

What that review concluded: the opening clock barely moved between games, and the losses were chess losses. Unused time was real, and spending the reserve was not, by itself, the fix. This sample does not describe Storm v4.

## Day 2, rounds 16–30

Fifteen games. [`ODIN_NEW_GAMES_REVIEW.md`](ODIN_NEW_GAMES_REVIEW.md) calls the day Storm's: 9 wins, 2 draws, 4 losses, 10/15 points.

Rounds 16–25, in [`ODIN_SITE_REVIEW.md`](ODIN_SITE_REVIEW.md) and [`ODIN_REVIEW.md`](ODIN_REVIEW.md): 6 wins, 1 draw, 3 losses. All nine decisive games were legal checkmates. The draw was a correct prospective threefold. Mean reserve was 16.929 seconds, or 11.015 seconds excluding round 19. The three losses averaged 4.548 seconds left.

What that review concluded: the miss was positional judgement and king-attack recognition, not a global increase in time spent.

Rounds 26–29 were wins against ChessML, JSP, and Neural Gambit, and a draw against FuzzyBot. Round 30 was a loss to Team1. The same review says those probes are not an unbiased win rate and are not a release score.

## Day 3, rounds 31–44

Fourteen games. I am not pooling them into one engine record. The log does not name the archive.

Rounds 31–34 are the reported Odin v5 upload in [`ODIN_DAY3_REVIEW.md`](ODIN_DAY3_REVIEW.md): 1 win, 0 draws, 3 losses. Win against xx. Losses against ms, AI Fellows, and adashima. All four were checkmates. That note says these games must not be attributed to v6. The lesson it recorded was earlier decision errors with time still on the clock, not a flag.

Rounds 35 and 36 are attributed in [`TEMPEST_IMPLEMENTATION_STATUS.md`](TEMPEST_IMPLEMENTATION_STATUS.md) to Odin v6. Both were checkmate wins, against Rush hour and Dogwarts. The note says the attribution is upload history, not a hash in the PGN, and that the wins still contained missed opportunities.

Round 37, Neural Gambit, was a loss by checkmate. The same note calls it another v6 game, from a different opening than the earlier Storm win against that name, and says not to read the pair as an engine regression.

Round 38, RMFE, was a fifty-move draw. [`TEMPEST_FRONTIER_RESEARCH.md`](TEMPEST_FRONTIER_RESEARCH.md) says not to assign this log to Odin v6 or Tempest r1. It also says the five-piece phase was drawn and should not be described as a thrown-away win.

Round 39, Gladiator, was a loss by checkmate. [`TEMPEST_ROUND39_REVIEW.md`](TEMPEST_ROUND39_REVIEW.md) identifies the upload as Tempest r1 and says the log has no archive hash. The lesson it recorded was a later queen trade into a bad ending, not the early attack as the whole story.

Round 40, PawnStorm, was a threefold draw. [`AGAMEMNON_RESEARCH.md`](AGAMEMNON_RESEARCH.md) records a legal 142-ply game with 4.006 seconds left, registered as a diagnostic and not used to fit that model.

Round 41, Alien Gambit, was a win by checkmate. [`AGAMEMNON_SCALE_STATUS.md`](AGAMEMNON_SCALE_STATUS.md) says the game was present and was not used for that fitting cycle.

Rounds 42, 43, and 44 were a loss to 50CentRaise, a win against Pwn, and a loss to xx, all by checkmate in the logs. I do not have a review in the repo that assigns those three an archive or a lesson.
