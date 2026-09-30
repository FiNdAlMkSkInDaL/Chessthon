# AI Chessathon

A chess agent built for [AI Chessathon 2026](https://aichessathon.com), with a local harness that uses the same protocol and clock.

I wanted to know whether a change helped before uploading, so I kept the official referee and measured the new engine against my previous one.

## What it is

The repository root, including `agent.py`, is the contest starter. The engine I measured is the separate package in [`storm/`](storm/).

A submission exposes one function, `get_move(fen, time_left_ms)`, in `agent.py` at the root of what gets uploaded. It receives the position as a FEN string and the remaining clock in milliseconds, and it returns a move in UCI notation, such as `e2e4`.

The official referee is included in [`harness/`](harness/). The version I used is recorded in [`lab/STARTER_SHA`](lab/STARTER_SHA).

[`baselines/`](baselines/) holds four small opponents that came with the starter:

- `random` plays any legal move.
- `greedy` looks one move ahead and counts material.
- `minimax` looks two moves ahead, scoring material and piece mobility, with no clock management.
- `numba` is that same two-move search, compiled with Numba so the evaluation runs faster.

The result table further down is a match between the engine in `storm/` and my previous engine. The four opponents above are an earlier practice ladder.

`make zip` packages the starter at the repository root. The archive I tested is a separate Linux build, and it is kept outside this repository. [`docs/STORM_V4.md`](docs/STORM_V4.md) describes that build.

## Local result

I played the engine in `storm/` against my previous engine. That previous engine was an earlier build, and I left its files unchanged for the match. The match was 40 games. This is a local comparison. The write-up is [`docs/STORM_V4.md`](docs/STORM_V4.md).

| Match | Games | Score | Record | 95% interval | Crashes, forfeits, or illegal moves |
|---|---:|---:|---|---|---:|
| New engine vs previous engine | 40 | 82.5% | 31 wins, 4 draws, 5 losses | 71.25–92.5% | 0 |

The interval is paired: both engines played the same openings. A crash, a time forfeit, or an illegal move would count in the last column. Both sides finished with none.

A separate check started from two openings taken from the contest site, each played once with each colour, and finished one win and three draws.

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

`make setup` installs dependencies with `uv sync`. `make play` is one game against `baselines/greedy` on the harness clock. `make arena` is 20 games against that same opponent. `python -m lab.storm.gates` checks that the engine in `storm/` still generates moves, searches, and answers inside the clock. It needs Python with `numpy`, `numba`, and `chess`. `.\dev.ps1 smoke` checks the starter `agent.py` at the repository root, through a repo-local `.venv`.

`make zip` runs `uv run python -m harness.package --include syzygy`. That zip is the starter at the repository root. Endgame tables for positions with three pieces left are optional. If `syzygy/` is absent, packaging skips that include, and the starter ignores the missing tables. I link Ronald de Man's tables rather than including them: <http://tablebase.sesse.net/syzygy/3-4-5/>. The starter only looks up positions with three pieces left.

## Layout

```
agent.py            starter entry point, get_move
storm/              the engine in the result table
tempest_exact/      a later engine, kept as its own record
baselines/          random, greedy, minimax, and numba
harness/            official referee, version recorded
lab/storm/          logs from the 40-game match
docs/STORM_V4.md    how that match was run
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
