# Chess TK — AI Chessathon 2026

Philosophy: [AGENTS.md](AGENTS.md). Build contract: [ENGINEERING.md](ENGINEERING.md).
Vendored starter harness is pinned in `lab/STARTER_SHA`. Do not edit `harness/`.

Windows inner loop: `.\dev.ps1 smoke` then `.\dev.ps1 perft`. Freeze zips are packed on Linux Python 3.12, not this ARM laptop.

## Current engine: Storm v4

Storm source is in [`storm/`](storm/), with its design, exact archive hash and
validation results in [`docs/STORM_V4.md`](docs/STORM_V4.md). The release is
[`dist/agent-storm-v4-linux-x86.zip`](dist/agent-storm-v4-linux-x86.zip), also
copied to Desktop `Storm-v4.zip` and the official upload file `agent.zip`.
It passed the fixed native 40-game match
against v3: **31 wins, four draws, five losses; 82.5% score**, with zero
operational failures on either side. The paired 95% score interval is
71.25–92.5%; the separate selected site-opening check finished one win and
three draws. These are local comparisons, not a measured leaderboard rank.

The signed v3 baseline remains [`dist/agent-v3-linux-x86.zip`](dist/agent-v3-linux-x86.zip).
Desktop `v3-agent.zip` preserves that exact v3 baseline. On 5 September the
user requested the desktop rename and made Storm the official `agent.zip`.
The user handles submission to the site; no upload was performed here.
The continuation prompt and working-state handoff are in
[`docs/STORM_CONTINUATION_PROMPT.md`](docs/STORM_CONTINUATION_PROMPT.md).

The ten Storm games from 5 September and the full v3 match have now been
reviewed for **Odin**, the next iteration. Read
[`docs/ODIN_REVIEW.md`](docs/ODIN_REVIEW.md) and
[`docs/ODIN_BUILD_BRIEF.md`](docs/ODIN_BUILD_BRIEF.md). The continuation prompt
now assigns Odin implementation; no Odin engine or new release is built yet.
The live referee now draws at 600 total plies, opening included. Historical
300-ply material rules and validation results below do not describe that update.

The starter commands below operate on the older files at the repository root.
**`make zip` does not package Storm.** Use the already tested Linux archive for
submission; repacking on Windows would produce different, untested bytes.

Storm checks and match tools live in `lab/storm/`; the unchanged official
referee remains in `harness/`. The 15 site-game analysis is in
[`docs/STORM_GAME_FORENSICS.md`](docs/STORM_GAME_FORENSICS.md).

For Storm's structural development checks with the installed Python 3.12:

```powershell
$stormPython = Join-Path $env:LOCALAPPDATA 'ChessTK\venv312\Scripts\python.exe'
& $stormPython -m lab.storm.gates
```

Windows runs are development evidence. Native release validation and packing
use the Linux signer described in the Storm validation document.

---



Fork this to build an agent for [AI Chessathon](https://aichessathon.com). It gives you a working
submission, baselines to beat, and a local harness that speaks the same protocol and enforces the
same clock as the platform, so you can see whether a change actually helped before you upload it.

```
git clone https://github.com/advitrocks9/aichessathon-starter
cd aichessathon-starter
make setup
make play
```

That plays your agent against a baseline over a full 120 s + 0.5 s game and prints the result.
For an unmodified starter checkout, `make zip` packages `submission.zip`.
In this repository, follow the Storm archive instructions above instead.

## Writing an agent

`agent.py` is the whole submission. One function:

```python
def get_move(fen: str, time_left_ms: int) -> str:
    return "e2e4"
```

The fork ships a legal random-mover, so the loop works before you write anything. Replace the body.

```
make play                                          # one game, real time control
make arena                                         # 20 fast games, prints a score
make play FEN="<fen>"                              # start from a given position
uv run python -m harness.play --black baselines/minimax --pgn game.pgn
uv run python -m harness.arena --opponent ../my-old-version --games 200
```

Anything your agent writes to stdout or stderr shows up under the result, so `print` debugging
works. The platform discards it during rated games and shows it in your validation log.

## The ladder

Measured with `harness/arena.py`. Beating greedy is a search. Beating minimax is a search plus an
evaluation worth searching with.

| Matchup | Games | Time control | Score |
|---|---|---|---|
| random vs greedy | 20 | 10 s + 0.1 s | 10.0% (+1 =2 -17) |
| greedy vs minimax | 6 | 120 s + 0.5 s | 0.0% (+0 =0 -6) |
| numba vs minimax | 6 | 10 s + 0.5 s | 66.7% (+2 =4 -0) |

- `baselines/random` plays a uniformly random legal move. It is what `agent.py` starts as.
- `baselines/greedy` searches one ply on material.
- `baselines/minimax` searches two plies on material and mobility, with no time management.
- `baselines/numba` is `minimax` with the evaluation jitted. It is barely stronger, which is
  the point: jitting a shallow search buys headroom, not depth. Read it for the warm-up call
  at the bottom, which is how you keep compilation off your clock.

## What's here

```
agent.py             your submission
baselines/           random, greedy, minimax, numba; each is a directory with an agent.py
harness/runner.py    the process the platform runs your agent in
harness/referee.py   the clock, legality, draw and adjudication rules
harness/rules.py     the event constants the harness enforces
harness/sandbox.py   the one process, spoken to as the platform speaks to a container
harness/play.py      one game between two agent directories
harness/arena.py     many games, with a score
harness/package.py   builds submission.zip with agent.py at the root
docs/IDEAS.md        where the strength actually comes from
```

Local games start from the normal position unless you pass `--fen`. Rated games start from
curated neutral positions.

The harness is here so your games are honest, not so you can pre-validate an upload. Acceptance
happens on the platform, and the validation log on your dashboard is the authority on it.

## The rules

[aichessathon.com/docs](https://aichessathon.com/docs) is canonical and changes. Read it before
you upload.
