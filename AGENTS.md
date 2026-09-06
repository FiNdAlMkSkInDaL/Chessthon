# Chess TK — what every coding agent must absorb

This is a **classical chess engine** for [AI Chessathon](https://aichessathon.com/docs), not a generic UCI bot, not a Kaggle net, not Stockfish-lite. Read this before writing code. The build contract is [ENGINEERING.md](ENGINEERING.md). If this file and `ENGINEERING.md` disagree, `ENGINEERING.md` wins; if either disagrees with the live site, **the site wins**. Re-fetch docs when a number or protocol might have changed:

- https://aichessathon.com/docs/agent-contract.md
- https://aichessathon.com/docs/rules.md
- Official starter: https://github.com/advitrocks9/aichessathon-starter — `harness/` is source of truth. Do not “improve” it.

Do not reopen doctrine that is already settled in `ENGINEERING.md` §0.1–0.3.

---

## Why we are building this

London is decided by a **13-round Swiss on a frozen zip**, then first-come invite replies. Hourly ladder Elo only seeds. One crash, flag, illegal UCI, init-timeout, or auto-claimed draw of a won game is a seat given away.

The contest already equalized the machine that *plays*: Python 3.12, 1 core, 2 GB, no GPU, no network, 60 s to `import agent` (ready only after import returns), 120 s + 0.5 s/move **wall**, process lives for one game. Everyone’s coding agent will dump the same CPW shopping list (magics, PVS, LMR, a tiny net). That list is the prior, not an edge.

**We win by being the least-broken searcher that plays *this* referee.** Reliability first. Depth second. Flavour never.

---

## Design philosophy

1. **This sandbox, not CCRL.** Unpublished curated openings. Referee auto-claims 3fold/50 *before* `get_move`. 300 plies of *this* game (`len(board.move_stack)` from the start FEN, stack starts at 0), then kingless material (P1 N3 B3 R5 Q9). Increment is credited *after* we return. Test midgame FENs, not `startpos`.
2. **Search beats theatre.** Numba bitboard alpha-beta + published PeSTO. `python-chess` is a FEN/UCI **root firewall**, not the hot loop. Do not `import torch` or onnxruntime in the agent (RAM + init). A CNN/PUCT mover is how you lose to depth on 1 core.
3. **Correctness before Elo tricks.** Perft-exact make/unmake before pruning. If Numba perft is red, the living searcher is python-chess ID+AB, not a buggy generator. Ray-loop sliders first; magics are not a correctness dependency and are **out of the freeze zip**.
4. **Never flag, never illegal, never gift a draw.** Iterative deepening always has a legal fallback. Hard clock margin is hundreds of ms, not 80. Panic: TT move or first legal — **no qsearch**. Qsearch in check generates **evasions** (no stand-pat). Root: if internal best is illegal, play any legal UCI.
5. **Play the auto-claim, not a textbook 3fold filter.** `board.outcome(claim_draw=True)` runs before we are asked. A draw can fire if *any* legal move would complete 3fold, or if `halfmove >= 99` and a quiet exists. Track `Board(fen)._transposition_key()` for every served FEN and after each **legal push of our UCI**. Do not infer opponent UCI from FEN deltas. When winning: no second occurrence of a key; at `halfmove >= 90` only zeroing moves. In search, repetition scores 0. 300-ply: count this game’s half-moves, not FEN `fullmove`; last 16 plies search with their material function and age the TT.
6. **Measure, then merge.** `last-good.zip` is sacred. Ladder is telemetry. Promote on perft + flag-rate 0 + smoke, not on two pretty games. At most one real SPRT if a Linux signer exists. LMR stays out without it.
7. **This laptop is a liar.** Windows ARM, Python 3.14, no Docker. Agent runtime of record is **Python 3.12**. Freeze zips are packed on a Linux x86_64 **one-agent signer** (`agent.py` at zip root). Never freeze a Windows ARM zip. The 4 GB VPS is that signer after collectors pause — not a train farm, not a two-core match replica. Do not put host logins, keys, or `.env` in the repo or any zip.
8. **Fewer, fatter `njit` functions.** Warm the exact dtypes search uses at import. `/tmp` is wiped every game; Numba cache does not survive. Abort import around 50 s rather than JIT on the clock. Native binaries, Cython, extra threads, `chess.py` on `sys.path`: forbidden.

---

## Freeze zip (what we actually ship)

**A + B + C.** Draw/adjudication logic is in **B**, not a late brick.

| In | Out |
|---|---|
| Perft-exact rays (or python-chess AB fallback) | Magic finder / magics rewrite |
| ID + fail-soft AB + middlegame clock + firewall | Ponder (TT across our moves is enough) |
| Qsearch (evasions if in check) + TT + ply-adjusted mates + ordering | Syzygy, Polyglot, nets, Texel-on-PeSTO |
| Vanilla PeSTO | Untuned pawn-structure bolted onto PeSTO |
| Panic without qsearch | LMR, IID, singular, ProbCut, `import torch` |

First **platform** upload is a legal mover so packaging/init/dashboard are known. Replace only with gated B/C.

Deliverable: `get_move(fen: str, time_left_ms: int) -> UCI`. Colour is side-to-move in the FEN. Module state lasts one game.

---

## Do not

- Ship Stockfish, Lc0, Maia, or a wrapper (retroactive DQ). SF-labelled *training* is allowed; it is not this week’s job.
- Re-litigate CNN / HalfKP / “the image has torch so we should use it.”
- Username-spray SSH. Console login only. No secrets in git.
- Edit `harness/` if the starter is vendored.
- Skip ahead in the DAG because a shopping list said LMR is +Elo.
- Treat nps, JIT seconds, or “200k is a seat” as facts until the Linux signer measures them.

If you want to add a search feature, name the gate it depends on and the test that keeps it. If you cannot, it does not ship.
