# AI Chessathon

A chess agent built for [AI Chessathon 2026](https://aichessathon.com), with a local harness that uses the same protocol and clock.

The engine I submitted was Athena. The archive is [`athena/agent.zip`](athena/agent.zip), and the same files are unpacked in [`athena/`](athena/). This repository also keeps the harness and an earlier engine.

## What was submitted

Athena was packed on 11 September 2026. [`athena/agent.zip`](athena/agent.zip) is that archive: 434,399 bytes, SHA-256 `b39bd59af11eb6d1a2b3fccab8c8719d01a3ef3e565549cdaff8325b6ed30b21`, with `agent.py` at the root of the zip.

`get_move(fen, time_left_ms)` receives the position as a FEN string and the remaining clock in milliseconds, and returns a move in UCI notation, such as `e2e4`. Athena checks a short opening book, then exact endgame tables for king and pawn versus king and for king and queen or rook versus king, then a Numba search. The evaluation uses PeSTO piece-square tables and a small network trained for this entry.

Before packing, I played that build against the previous Athena build in the same working folder. Each screen was 8 games, one at a time, at 500 milliseconds a move, and stopped at 160 plies. That is a laptop filter. The contest clock is 120 seconds plus 0.5 seconds a move.

| Screen | Games | Score | Record |
|---|---:|---:|---|
| Positions kept aside | 8 | 5.0/8 | 2 wins, 6 draws, 0 losses |
| Starting positions, first run | 8 | 4.5/8 | 2 wins, 5 draws, 1 loss |
| Starting positions, rerun | 8 | 6.5/8 | 6 wins, 1 draw, 1 loss |
| Four openings used earlier | 8 | 6.0/8 | 4 wins, 4 draws, 0 losses |

The first run on the starting positions scored 4.5/8. I reran that screen, then packed after the four-opening screen scored 6.0/8. These are small local screens. A public rating would come from the contest site.

## Earlier engine in this repository

The engine in [`storm/`](storm/) is an earlier build. I played it against the build before that one, using the earlier build's files unchanged. The match was 40 games. This is a local comparison. The write-up is [`docs/STORM_V4.md`](docs/STORM_V4.md).

| Match | Games | Score | Record | 95% interval | Crashes, forfeits, or illegal moves |
|---|---:|---:|---|---|---:|
| Earlier engine vs the build before it | 40 | 82.5% | 31 wins, 4 draws, 5 losses | 71.25–92.5% | 0 |

The interval is paired: both engines played the same openings. A crash, a time forfeit, or an illegal move would count in the last column. Both sides finished with none.

A separate check started from two openings taken from the contest site, each played once with each colour, and finished one win and three draws.

The repository root, including `agent.py`, is the contest starter. [`baselines/`](baselines/) holds four small opponents that came with that starter:

- `random` plays any legal move.
- `greedy` looks one move ahead and counts material.
- `minimax` looks two moves ahead, scoring material and piece mobility, with no clock management.
- `numba` is that same two-move search, compiled with Numba so the evaluation runs faster.

The 40-game table is the earlier engine. These four opponents are a practice ladder from before that.

`make zip` packages the starter at the repository root. The uploaded archive is the file already stored at [`athena/agent.zip`](athena/agent.zip). The Linux archive I tested for the earlier engine is kept outside this repository. [`docs/STORM_V4.md`](docs/STORM_V4.md) describes that build.

The official referee is included in [`harness/`](harness/). The version I used is recorded in [`lab/STARTER_SHA`](lab/STARTER_SHA).

## Practice ladder

Measured with the harness, before the engine in `storm/`. Beating greedy takes a search. Beating minimax takes a search and an evaluation worth searching with.

| Matchup | Games | Time control | Score |
|---|---:|---|---|
| random vs greedy | 20 | 10 s + 0.1 s | 10.0% (+1 =2 -17) |
| greedy vs minimax | 6 | 120 s + 0.5 s | 0.0% (+0 =0 -6) |
| numba vs minimax | 6 | 10 s + 0.5 s | 66.7% (+2 =4 -0) |

Time control is the starting clock plus a small increment added after each move. The score in parentheses is wins, draws, and losses for the first opponent.

## Run

Bash, from the repository root:

```bash
make setup
make play
make arena
python -m lab.storm.gates
```

PowerShell, without `make`:

```powershell
uv sync
uv run python -m harness.play --white . --black baselines/greedy
uv run python -m harness.arena --opponent baselines/greedy --games 20
python -m lab.storm.gates
.\dev.ps1 smoke
```

`make setup` installs dependencies with `uv sync`. `make play` is one game against `baselines/greedy` on the harness clock. `make arena` is 20 games against that same opponent. `python -m lab.storm.gates` checks that the earlier engine in `storm/` still generates moves, searches, and answers inside the clock. It needs Python with `numpy`, `numba`, and `chess`. `.\dev.ps1 smoke` checks the starter `agent.py` at the repository root, through a repo-local `.venv`.

`make zip` runs `uv run python -m harness.package --include syzygy`. That zip is the starter at the repository root. Endgame tables for positions with three pieces left are optional. If `syzygy/` is absent, packaging skips that include, and the starter ignores the missing tables. I link Ronald de Man's tables rather than including them: <http://tablebase.sesse.net/syzygy/3-4-5/>. The starter only looks up positions with three pieces left.

## Layout

```
agent.py            starter entry point, get_move
athena/agent.zip    the archive that was uploaded
athena/             those same files, unpacked
storm/              earlier engine, the 40-game match
tempest_exact/      another engine copy, kept as its own record
baselines/          random, greedy, minimax, and numba
harness/            official referee, version recorded
lab/storm/          logs from the 40-game match
docs/STORM_V4.md    how that earlier match was run
docs/results.md     games played on the contest site
docs/experiments.md notes on the other engine copies
docs/lab/           build notes
LICENSE
```

## Limits

This is a contest entry and a research record. A public rating would come from the contest site, and that site's validation log is what decides whether an upload is accepted.

The live referee draws a game after 600 plies, counting the opening. A ply is one half-move. Earlier notes stop some games at 300 plies and decide them by material. Those notes describe earlier tests. The current rule is the 600-ply draw.

Games on the contest site are summarised in [`docs/results.md`](docs/results.md). Later copies of the engine are summarised in [`docs/experiments.md`](docs/experiments.md). Build notes are in [`docs/lab/`](docs/lab/).

## License

MIT. See [LICENSE](LICENSE).

If something looks wrong, open an issue.
