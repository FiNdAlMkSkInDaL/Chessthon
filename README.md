# AI Chessathon

A chess agent built for [AI Chessathon 2026](https://aichessathon.com), with a local harness that uses the same protocol and clock.

I wanted to know if a change helped before uploading, so I kept the official referee and measured against my own previous engine.

## What it is

Storm v4 is in [`storm/`](storm/). The submission surface is `get_move(fen, time_left_ms) ->` a UCI move, in `agent.py` at the root of a submission. The official referee is vendored in [`harness/`](harness/) and pinned in [`lab/STARTER_SHA`](lab/STARTER_SHA). I left that harness alone.

[`baselines/`](baselines/) is the starter ladder: random, greedy, minimax, and numba. That ladder is not Storm's result.

`make zip` packages the starter at the repository root, not Storm. The tested Storm Linux archive is built by the Linux signer described in [`docs/STORM_V4.md`](docs/STORM_V4.md). It is not in git.

## Local result

Storm v4 against my signed v3 baseline, on a fixed native 40-game match. This is a local comparison, not a leaderboard rank. The write-up is [`docs/STORM_V4.md`](docs/STORM_V4.md).

| Match | Games | Score | Record | Paired 95% interval | Operational failures |
|---|---:|---:|---|---|---:|
| Storm v4 vs signed v3 | 40 | 82.5% | 31 wins, 4 draws, 5 losses | 71.25–92.5% | 0 |

A separate site-opening check finished one win and three draws.

## Starter ladder

Measured with the harness, before Storm. Beating greedy takes a search. Beating minimax takes a search and an evaluation worth searching with.

| Matchup | Games | Time control | Score |
|---|---:|---|---|
| random vs greedy | 20 | 10 s + 0.1 s | 10.0% (+1 =2 -17) |
| greedy vs minimax | 6 | 120 s + 0.5 s | 0.0% (+0 =0 -6) |
| numba vs minimax | 6 | 10 s + 0.5 s | 66.7% (+2 =4 -0) |

## Run

Bash, from the repository root:

```bash
make setup
make play
make arena
python -m lab.storm.gates
```

PowerShell, the same three harness targets without `make`:

```powershell
uv sync
uv run python -m harness.play --white . --black baselines/greedy
uv run python -m harness.arena --opponent baselines/greedy --games 20
python -m lab.storm.gates
.\dev.ps1 smoke
```

`make setup` is `uv sync`. `make play` is one game against `baselines/greedy` at the harness clock. `make arena` is 20 games against that same opponent. `python -m lab.storm.gates` is Storm's structural gate. It needs Python with `numpy`, `numba`, and `chess`, and it reads `storm/` unless `STORM_SOURCE` is set. `.\dev.ps1 smoke` checks the root agent through a repo-local `.venv`, not the Storm gate.

`make zip` runs `uv run python -m harness.package --include syzygy`. That zip is the root starter. If `syzygy/` is absent, the extra include is skipped. Three-piece Syzygy WDL+DTZ is optional: a missing `syzygy/` directory is a no-op in the starter. I do not ship the files. Ronald de Man's tables are at <http://tablebase.sesse.net/syzygy/3-4-5/>. The starter only probes three-piece positions.

## Layout

```
agent.py            starter get_move
storm/              Storm v4
tempest_exact/      later candidate; not the table above
baselines/          starter ladder
harness/            pinned official referee
lab/storm/          local Storm v4 match evidence
docs/STORM_V4.md    how the 40-game match was run
docs/results.md     site-log summary
docs/experiments.md what the other engine copies were
docs/lab/           build notes
LICENSE
```

## Limits

This is a contest entry and a research record. It is not a rated-engine claim. Acceptance is the platform validation log.

The live referee draws at 600 total plies, opening included. Notes about a 300-ply material adjudication describe the historical Storm tests, not the current rule.

Site games are summarised in [`docs/results.md`](docs/results.md). They are not a leaderboard rank. Later copies are summarised in [`docs/experiments.md`](docs/experiments.md). Build notes, including the old agent handoffs, are in [`docs/lab/`](docs/lab/).

## License

MIT. See [LICENSE](LICENSE).

If something looks wrong, open an issue.
