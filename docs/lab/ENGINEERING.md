# AI Chessathon — Engineering Bible

**Agents:** read [AGENTS.md](AGENTS.md) first (philosophy and freeze cut). This file is the build contract.

Status: living document. Canonical competition rules remain [aichessathon.com/docs](https://aichessathon.com/docs). If this file and the site disagree, the site wins.

**Agamemnon backed-up decision cycle, 6 September 2026 (in progress):** read
`docs/AGAMEMNON_DECISION_RESULTS.md` and `lab/agamemnon_decision/`.
Actual PV endpoint/refutation collection covers2,880 game/opening families;
the broader settled dataset retains11,582 leaves. Thirty-two distinct fits
plus six deterministic snapshot reruns compare preference/static/mixed/replay
objectives and an original16-unit residual head. Seventeen Linux variants
completed3,740 development decisions. Mixed25 scored6W/6D/4L against Tempest;
replay25 scored7W/6D/3L and earned independent-confirmation eligibility.
Settled-pair25 finished4W/10D/2L. The requested15/20/25/30/35% sweep completed:
25% remained best tested (15.26cp mean wall regret across two repeat controls);
no neighbour earned a direct match. Totals:23 probe executions,5,060 decisions,
48 complete development games and6,735 legal plies. Replay25's exact Linux
archive (`a7233886...`) passed native/protocol/resource gates and is now playing
24 full-clock games on the12 reserved confirmation families, two VPS lanes.
Those12 families are now consumed;320 sealed Lichess roots remain untouched.
This is bounded confirmation, not the112-game release guard. No outside-git archive
promotion occurred. Tempest r1 remains `agent.zip` (`0ed607e2...`).

**Agamemnon frontier sandbox, 6 September 2026:** read
`docs/AGAMEMNON_FRONTIER_RESULTS.md` and `lab/agamemnon_scale/frontier/`.
Fourteen additional training fits and eleven candidate variants completed:
king-relative incremental context, move-preference/replay objectives, hybrid
evaluation, bounded corrections, separate pruning evaluation, and adaptation on
2,496 sampled actual qsearch states. Twelve Linux variants including Tempest
completed 2,640 equal-node/equal-wall development decisions with perft, accumulator
parity and reset gates. No candidate cleared the predeclared nomination rule;
no new matches, confirmation opening use, or an archive promotion. All experiment
services completed. Tempest r1 remains `agent.zip`. The next proposed objective is
own-search backed-up quiet-leaf preferences with refutations and broader root
families, rather than assuming lower static error guarantees stronger play.

**Agamemnon scaled training, 6 September 2026:** see
`docs/AGAMEMNON_SCALE_STATUS.md` and `lab/agamemnon_scale/`.
The public corpus now contains4,106,090 filtered unique training positions.
Million- and four-million-position original neural pretraining, incremental
native evaluation and upper-tree learned branch allocation are implemented.
Lower static error has not yet established a Tempest replacement: the first
neural leaf evaluator lost its16-game development screen; the first learned
advisor scored50% against Tempest. Turn-aware mover/opponent heads passed
native gates and improved error against same-data/update controls, but scored
40.625% against Tempest. This completed cycle contains64 value-model fits and
96 development games; no candidate earned promotion. No experiment service
remains active. Tempest r1 remains unchanged.

**Agamemnon architecture reopening, 6 September 2026:** the user explicitly
requested a new generation focused on architectural ceiling and broad research,
including reopening the prior neural/search cuts. Read
`docs/AGAMEMNON_RESEARCH.md` and `docs/AGAMEMNON_BUILD_SPEC.md`.
One hundred original training fits, public-data acquisition, policy-budget math,
and an incremental neural search prototype are completed in `lab/agamemnon/`.
Public pretraining followed by search-state adaptation is promising; quiet/tail
regressions and playing strength remain unresolved. Linux incremental/refresh
search identity passed24 comparisons with CPU assignments swapped. This is R&D,
not promotion: the signer archive (not in git) remains Tempest r1 (`0ed607e2...`).
Live rules re-fetched today permit original trained models and engine-labelled
training data; third-party engines/ports, published networks and runtime engine-
answer databases remain prohibited. No new full-clock match or release was made.

**Compounding implementation completed, 6 September 2026:** read
`docs/TEMPEST_COMPOUNDING_RESULTS.md` and `docs/TEMPEST_ROUND39_REVIEW.md`.
Six 16-game development screens (96 games, 13,287 legal plies) produced no
strength-confirmation nominee. A 5.30 MB tablebase-only candidate passed Linux
archive/native/protocol checks and remains unpromoted in `lab/tempest_edges/`.
the signer archive (not in git) is still Tempest r1 (`0ed607e2...`). Fresh confirmation
families remain unused; no 112-game run was launched for these candidates.

**Compounding Tempest edges, 6 September 2026:** read
`docs/TEMPEST_COMPOUNDING_PLAN.md`. Four isolated optimization variants passed
192 fixed-node identity runs; lazy pawn-threat evaluation measured about 2.2%
faster on twelve selected Linux diagnostic roots. This is development timing,
not Elo evidence. No archive promotion; the narrower chess policy remains
inconclusive. New frozen artifacts live in `lab/tempest_stack/`.

**Further Tempest R&D, 6 September 2026:** read
`docs/TEMPEST_FRONTIER_RESEARCH.md` for the new search/ordering experiments and
round-38 RMFE draw review. These are isolated research candidates; the outside-git archive
release and canonical `tempest_exact/` source remain unchanged.

**Tempest implementation, 6 September 2026:** the official starter at
`284724ab56cecb2a1a9a4e5769b4748adab4ed90` now uses `board.outcome()`,
then an **actual third repetition** and **actual fifty moves**, then the 600
absolute-ply cap. Intended-next-move claims are no longer referee terminals.
The new untouched harness is in `lab/tempest_build/official-284724ab/`.
**the signer archive (not in git) is now Tempest r1**, hash beginning `0ed607e2`, canonical
source `tempest_exact/`. It adds original exact KQK/KRK tables and the corrected
fifty-move predicate. It passed exhaustive table checks, native deployment and
a 12-game short smoke (5W/4D/3L); this is not a general Elo-leap claim.
`tempest/` remains the rules-only fallback. Odin v6 is preserved. The neural
and linear pilots did not meet their gates and are excluded. Read
`docs/TEMPEST_R1_RELEASE.md` and `docs/TEMPEST_IMPLEMENTATION_STATUS.md` first.

**Odin v6 release, 6 September 2026:** `odin_v6/` is the current released
source. the signer archive (not in git) is the exact Linux archive beginning `cd3ed778`,
after112 full-clock games against v5:30W/69D/13L,57.59%, paired95% lower bound
52.23%, zero operational failures. V5 remains preserved. Read
`docs/ODIN_V6_RELEASE_REPORT.md` and `docs/ODIN_DAY3_REVIEW.md` before continuing.

**Odin review, 5 September 2026:** the user named the next iteration Odin and
requested a concrete implementation handoff based on ten Storm site games
and the Storm-v3 matches. Read `docs/ODIN_REVIEW.md` and
`docs/ODIN_BUILD_BRIEF.md`. The live contract and official starter re-fetched
today now use **600 total plies including the opening, then a draw**, with
normal automatic outcomes checked first (`board.ply()`, not move-stack length).
All older 300-ply material-adjudication instructions below are superseded.
Storm's archive remains unchanged; Odin must correct the old mode, clock cap
and fixed history-buffer assumptions. Preserve historical `harness/` for
reproduction and validate Odin in a separate, untouched, commit-pinned copy
of the current official starter. This review did not implement or submit Odin.

**Storm v4 reopening, 4 September 2026:** the user explicitly authorized a new
strength-focused design and reopened the earlier feature cuts below. Storm is
developed separately in `storm/`. On 5 September
the signer archive (not in git) became the tested Storm v4 release; the exact old v3
archive is preserved as the preserved v3 archive (not in git).
LMR, improved evaluation throughput and adaptive time control may enter Storm
only after their correctness tests and measured matches. Earlier freeze-week
prohibitions on experimenting with these features do not veto this work.
The live contract re-fetched at 22:30 UTC now specifies **90 s initialization**,
one core of an **AMD EPYC 9V74 at 2.60 GHz**, **10 uploads/day**, and suspension
while the opponent thinks. References below to 60 s, six uploads, unpublished
CPU or free pondering are historical and superseded by the live site. The
unchanged official harness already uses the 90 s limit. No third-party engine,
translation, published network or runtime engine-answer database is allowed.

Council closed 2 Sep 23:53. Red-team 3 Sep 00:28 folded into §0.3. Brick 0–C closed (review APPROVE). Lab gauntlet + private openings exist; they measure flag-rate/SPRT, they do not train PeSTO. Linux signer still required before a freeze-candidate zip.

This is not a brainstorm. It is the build contract for a classical search engine that is *purpose-built for this sandbox*, not for CCRL, not for Lichess, not for a Kaggle notebook.

---

## 0. Doctrine

We do not try to be Stockfish. We do not try to be AlphaZero. We do not one-shot a CNN.

We fight a contest that has already told us its physics:

- 1 CPU core, 2 GB, no network, no GPU, Python 3.12
- wall-clock 120 s + 0.5 s/move, 60 s to JIT/load
- unpublished curated openings
- referee auto-claims threefold and fifty-move
- 300 plies then **material adjudication** (kingless material)
- crash / flag / illegal = loss, no retries
- 13-round Swiss on a **frozen** zip seeds London seats. Seats then fill in that seed order, one per UK member, at most 2 per team, **confirmed by reply, first come**. Odd field: 1-point bye.
- process lives for one game; core stays ours while they think

Hannibal: we do not meet the field on “who trained the fanciest net.” We meet them on axes we control and they will neglect.

| Axis we own | Why it wins Swiss games |
|---|---|
| Untouched official harness | We test claim_draw, 300-ply stack, and clocks against their referee.py |
| Numba bitboard search | 100–1000× the node rate of `python-chess` in the hot loop |
| Iterative deepening + clock panic | Flagging is the most common self-inflicted loss |
| Ponder after `get_move` returns | Free depth on *their* clock **if** stop-join; a racy shared TT is a Swiss loss |
| Anti-repetition when ahead | Full-game chain, both colours; referee will steal wins we thought we had |
| 300-ply material policy | Unique to this contest; last ~20 plies scored their way at the **root** |
| Reliability gates | One crash in 13 Swiss games is a seat we do not get |
| SPRT vs previous zip | Promote on pentanomial; laptop 1-core affinity + Linux replica smoke |

The interlocking web is the point. Search quality depends on move ordering. Move ordering depends on the TT and the eval. The TT is only useful if the process lives (it does). Pondering is only useful if we keep a PV (search does). Time management is only useful if ID always has a move (it does). The replica is only useful if every change is measured against it. None of these features is a solo hero. They are a circuit.

### 0.1 Council reconciliation (binding unless we reopen it)

Three briefs plus the laptop inventory. Where they agree, that is now doctrine. Where they clash, **1-core contest physics** and **this 4 GB box** break the tie — not a calendar.

**Unanimous — do not reopen without new evidence**
- Classical Numba search, not a CNN/PUCT mover. Torch in the image is bait.
- First upload is boring, legal, timed, flag=0. If Numba perft is red, that zip is python-chess AB.
- Replica envelope is Docker 1 CPU / 2 GB / no net / their referee **untouched**. Local `play.py` is not the platform.
- Do not `import torch` or onnxruntime in the agent (RAM + init). Do not multiprocessing inside the agent.
- Never freeze a Windows ARM zip. Measure nps in Linux 1-core.
- Maxing the VPS for SGD / nets is the wrong main goal. One-agent **signer** uptime is the right one.

**Build order (dependency, not dates)**
- Gate 1 is **perft-exact ray-loop bitboards**, not magics. Copied magic numbers only after Linux nps is measured, and only if that nps is < ~250k.
- Elo after a legal searcher exists is qsearch + TT (64–128 MB, never 1 GB) + middlegame time panic + ordering. PVS after hash-move+killers exist. **RFP before LMR.** LMR is SPRT-gated. **IIR, not IID.** NMP without verification search; NMP only with non-pawn non-king material.
- Never store unadjusted mate scores in the TT. Ply-adjust on store/probe; test ~15 positions.
- **Skip Polyglot.** Skip Texel-on-published-PeSTO-PSTs. Freeze eval is vanilla PeSTO. No pawn-structure forest this week.

**Protocol traps**
- Auto-claim is **before** `get_move`. Track `_transposition_key()` of served FENs and after our legal pushes. Do not infer opponent UCI. Winning: no second occurrence; halfmove ≥ 90 must zero.
- No ponder in the freeze zip.

**ML sidecar:** out this freeze week. Not because physics forbids a tiny ONNX eval.

**Syzygy:** skip this freeze week.

Target gates: **flag=0, illegal=0, import ready within 60 s, freeze zip = A+B+C.** nps is measured on the signer, never a bible promise.

### 0.2 The real edge (binding)

The field will ask the same class of coding agent the same question. The answers will converge: Numba, PeSTO, magics, PVS, LMR, maybe a tiny net. **That shopping list is not an edge.** It is the prior.

**The contest already equalized the machine that plays.** 1 core, 2 GB, Python 3.12, no net, no GPU, same clock. A bigger VPS does not make `get_move` search deeper in Swiss. A GPU farm does not either. Hardware we do not have is not a strength.

**The 4 GB box is a one-agent Linux signer, not a cluster and not a match replica.** Uptime is useful. After collectors pause, run **one** contest-shaped process: cold init, nps, pack freeze zips. Do not run both colours under `--cpus=1` and believe the clocks. Contest CPU is unpublished; Numba codegen will not match. Console login is still pending — until then, nps gates are guesses.

It is **not** a training box:

- The contest image has no Stockfish. Labels cannot be produced *inside* the identical env.
- The replica is capped at 2 GB / 1 core on purpose. That is the right shape for *measuring* an agent and the worst shape for *fitting* weights.
- PeSTO does not learn from self-play. Game-result Texel on noisy student games is how you make eval worse. Self-play of zip A vs zip B is **SPRT**, not training.
- internwatch + CRL already own this box’s RAM. Replica + those + a train job OOMs. Pause the collectors for Chessathon windows, or the replica loses.

So: always-on replica / gauntlet = yes. Torch or Texel *inside* that container = no. If RAM is left on the **host** after the replica is up, a Stockfish eval stream may label extra terms — that process is *beside* the replica, never in it. The net still defaults out.

**What actually separates AI-assisted teams**

| They will do (same prompt, same week) | We do instead |
|---|---|
| Ship the CPW shopping list in date order | Ship the next brick only when the previous gate is green |
| Trust laptop nps | Measure in the replica; this ARM box is a liar |
| `import torch` because it is in the image | Never import it |
| Magics / LMR / a net first | Perft → never-flag ID → qsearch/TT/time → referee physics |
| Track FENs they were asked | Full-game zobrist, both colours |
| Daemon ponder on a shared numpy TT | Stop-join, or no ponder |
| Overfit the hourly ladder, last upload wins | `last-good.zip`; ladder is telemetry |
| Follow Luma (NN required, top 16) | Live site: Swiss 13, classical is a full entry |

That table is the edge. It is process, replica fidelity, and *this* protocol — not FLOPs.

**Play to what we already have, not what we wish we had**
- Ops muscle from a real VPS (polymarket / CRL patterns): do not `apt upgrade` a 4 GB box into an OOM. Other students with a server will.
- ARM laptop as a forcing function: we *must* sign on Linux. x86 Cursor users will believe local nps and get surprised at freeze.
- Already discarded the Luma page. Other agents still quote it.
- Written skip list that the next chat will try to violate. The bible exists so we do not re-litigate magics every session.
- Optional, and only if it is cheap: a second human (logs, ladder PGNs, Daily Five wildcard — room seat, not bracket). A UCL x86 Linux lab machine would be a *better replica host* than this overloaded 4 GB VPS. That is still identity, not a farm. Do not rent GPUs.

**Do we need more hardware?** No farm. We need a Linux x86_64 **signer** (this 4 GB box after collectors pause, or a UCL lab PC) before any zip is a freeze candidate. Perft and legal-move work do not wait on that box. If freeze arrives, we ship last-good: a never-flag searcher, not a half-integrated DAG.

### 0.3 Red-team of 3 Sep (how we use reviews)

Independent Ask-mode review. Live starter `harness/referee.py` was re-read after it. This is the process: **verify harness-dependent claims, accept physics/rules hits into this file, reject items that block clone or re-open the classical thesis.** We do not keep two bibles. We do not re-litigate accepted cuts.

**Accepted — now binding**

- Freeze-week target is **A + B + C**, with draw/adjudication logic **inside B**, not a late Brick E. Cut from freeze zip: G, F, magics, ponder, extra-term Texel, contempt grids, per-brick SPRT. D is opportunistic (RFP/NMP/SEE only if C is green and flag-rate is 0).
- Replica is a **one-agent Linux signer**, not a bit-identical match. Contest: two agents share a machine, two dedicated cores, unpublished CPU. `--cpus=1` running both colours serialises thinking and lies about ponder/nps. Do not say “bit-identical.”
- 300-ply: `len(board.move_stack) >= 300` from the **curated start** (`move_stack` begins at 0). Do **not** use FEN `fullmove`. Count plies of this game. Switch late (`300 - ply <= 16`), age/clear TT, search with the same kingless material function the referee will use.
- Auto-claim is **before** `get_move` (`board.outcome(claim_draw=True)`). python-chess 1.11 `can_claim_threefold_repetition()` is true if the current position is already 3fold **or any legal move would complete one**. Fifty: claim at `halfmove >= 100`, or `>= 99` if a non-zeroing legal move exists. Root-filtering the move we *would* have played does not run. Keep `Board(fen)._transposition_key()` for every served FEN and after each **legal push of our UCI**. Do not infer opponent UCI. When winning, avoid a second occurrence (a later legal return auto-draws). When winning and `halfmove >= 90`, zeroing is mandatory. In search, a repetition scores 0.
- Qsearch: if in check, generate **evasions**, no stand-pat. Checks-as-captures stay off until nps is measured.
- Time: leftover milliseconds, not `time_left - 30`. Hard margin hundreds of ms (GC + `Board(fen)` + firewall after nogil). Panic: no qsearch. Increment is credited **after** return. Check the clock inside the loop. Watchdog `+500` kills hangs; it does not forgive a flag (`clock < 0` after wall time).
- SPRT: at most **one** real SPRT this week if the signer exists. Otherwise: perft, ~20 games flag=0 at fast TC, 2-game real-TC smoke. LMR stays out without that SPRT.
- JIT: 40 s is unevidenced. Warm the exact signatures search uses. Abort import if warmup exceeds ~50 s (fail validation, do not flag game 1). `cache=True` does not survive `/tmp` wipe. Measure cold init on the Linux signer.
- First platform zip this week is a **legal mover** (starter or python-chess random/greedy) from Linux if possible, so packaging/init/dashboard are known. Replace only with gated B/C. `last-good` starts there.
- No ponder in the freeze zip. TT persistence across our moves is the free protocol Elo. `join(50ms)` is a race.
- Store ply-adjusted mates in the TT (unit-test ~15 positions). Do not ship “never store mates.”
- Eval freeze: **vanilla PeSTO** (material + PST + taper). Bishop pair only after a sanity check. No pawn-structure forest this week (double-counts tuned PSTs).
- Skip Syzygy this week. Packager default is `*.py` + `weights/` — subdirs need `--include`.
- Init-kill is no `{"ready": true}` within 60 s of **process start**; runner writes ready only after `import agent` returns.
- Python **3.12** is the agent runtime of record. Laptop 3.14 / numba 0.66 is syntax. WSL on this machine is still aarch64. Zips built on the Linux signer (`agent.py` at archive root).
- Host login material does not live in this file or in any zip.
- Tiny ONNX/int16 nets are not forbidden by 1-core physics; they are out **this week** because we have no labels, no time, and no SPRT. A rival with a small ONNX eval is possible. Do not cope by claiming physics.

**Rejected or narrowed**

- “Not ready to clone.” We are not ready to **freeze**. Clone + legal `get_move` is how we learn the platform. Linux signer is required before a zip is a freeze candidate, not before `git clone`.
- “Do not start Brick A until the signer exists.” Perft vs `python-chess` is correctness. nps gates wait on the signer.
- “Do not clone until registered / 3.12 installed.” Register before first **upload**. Install 3.12 in parallel with clone. Do not commit secrets.
- Reopening a CNN/PUCT mover or magics-first. The reviewer’s own verdict: classical Numba + PeSTO is the right sport.
- Treating 200k nps / 50-seat Elo as a promise. Those numbers stay as **hopes**, measured on the signer, never as bible facts.

**The remaining edge (adult, not poetry):** among competent Numba PeSTO + TT rivals, we win by not flagging, not returning illegal UCI, not auto-claim-drawing a win, not init-timeout, not crashing on EP/promo. Draw logic in B is that edge. It is not optional flavour.

---

## 1. What “winning” actually means

### 1.1 The real tournament

Hourly Elo is a toy. It seeds the Swiss. The Swiss is 13 games of the **locked** build. London seats then fill in Swiss seed order, one UK member, max 2 per team, **reply first-come**. Be in a position to confirm.

A Swiss with 13 games has huge variance. A 100-Elo gap is only ~64% expected score. A 300-Elo gap is ~85%. To *blow the field away* we want ≥300 Elo over the median finalist, and ≥0 crash/flag/illegal rate.

### 1.2 Honest strength model

Published baselines (starter README):

- random vs greedy: 10%
- greedy vs 2-ply minimax: 0% over 6 full-clock games
- jitting that same 2-ply search: almost nothing — speed without depth is a trap

Field we will actually face, ranked:

1. Starter random / greedy / shallow minimax — dead.
2. `python-chess` + alpha-beta + PeSTO, no JIT — ~5–20k nps, depth 4–6 in the middlegame. Tactical. Beat by seeing one ply further.
3. Tiny CNN / policy-MCTS (there is already a public PR attempting this). On 1 CPU core a convnet is tens-to-hundreds of evals/sec. They will miss tactics. Beat by search.
4. Someone who also read Chess Programming Wiki and JITs a bitboard engine. **This is the real final.** We beat them on search features, time management, pondering, contest-specific rules, and not crashing.
5. Organiser house bots (CCRL-rated, cannot qualify). Use them as a measuring stick on the ladder, not as a target.

Target for freeze: **flag=0, illegal=0, import ready < 60 s, a searcher that is perft-correct or firewalled, with qsearch+TT and referee draw logic.** nps is measured on the Linux signer, not wished. One crash ≈ one seat. We will not be 2800. We do not need to be. We also do not get 200k nps by writing it down.

We do not need 3000 CCRL. We need to be the least-broken, deepest-searching Python engine in a room of students.

---

## 2. What we will not do

These lose weeks:

- Train a big Torch net and call it from every leaf. 50 evals/sec is a policy model’s budget, not a search eval’s. Organisers said this themselves.
- Ship Stockfish, Lc0, Maia, or a wrapper. Instant, possibly retroactive, DQ.
- Cython / native `.so`. Rejected.
- Multiprocessing, `torch.set_num_threads(>1)`. One core; extra threads steal from ourselves.
- Opening book keyed on startpos **or** a middlegame Polyglot. Curated unpublished FENs; an 8% hit / 1% lemon loses a Swiss game.
- Magic *finder* from scratch. Copied CPW numbers only after Linux nps is measured, and only if that nps is < ~250k.
- `import torch` / onnxruntime in the agent (RAM + 60 s init).
- Texel-retune of published PeSTO PSTs on a small noisy set (Zurichess-class Elo loss).
- IID. Use IIR. LMR before killers+history+TT-move.
- Full 5-man Syzygy (378 MB WDL alone). Cap is 50 MB unzipped.
- Singular extensions, ProbCut, continuation-history forests before A–E are green.
- Daily Five as a primary path. Wildcard is a seat in the room, not the bracket.
- One-shot “write the whole engine in one sitting.” Foundations first.
- Username-spray SSH at the VPS (`root`/`ubuntu`/`debian` already denied). Console login only.

CNN / PUCT / policy-only as the mover: dead. HalfKP: dead. A 768→32→1 drop-in is a sidecar on leftover RAM. Shipping still requires SPRT vs PeSTO. If it is not green, it does not ship. On this 4 GB VPS, **identity replica first**.

---

## 3. Architecture — one process, two worlds

```
get_move(fen, time_left_ms)
        │
        ├─ python-chess Board(fen)     # root only: parse, legal check of chosen UCI
        ├─ encode → numba Position     # 12 bitboards + occ + castle + ep + hash
        ├─ stop_ponder()  # freeze zip: no ponder thread; this is a no-op
        ├─ if fen == ponder_hit: keep TT (maybe skip shallow ID)
        ├─ else: keep TT anyway (siblings); do not clear
        ├─ iterative deepening on OUR clock (single thread, nogil)
        ├─ python-chess legal firewall on chosen UCI
        ├─ record full-game zobrist (served FEN + after our move)
        ├─ spawn ponder on predicted child   # NOT in freeze zip; TT persistence is enough
        └─ return UCI
```

`python-chess` is a **FEN/UCI adapter and a root legality firewall**. It is not the searcher. Searching with `board.push` / `list(board.legal_moves)` at every node is how the starter baselines stay weak.

The hot path is Numba `@njit(nogil=True, cache=True)`:

- ray-loop sliders + precomputed leapers (copied magics later, never a finder)
- make / unmake (no copy)
- eval (tapered PeSTO + a few cheap terms)
- ID + fail-soft AB; PVS only after ordering exists
- TT probe/store (64 MB; **ply-adjusted mates**; unit-test before store)
- SEE, MVV-LVA, killers, history

Warm **every** jitted function at import with the real dtypes, inside the 60 s init. Cache does **not** survive across games (fresh process; `HOME` → `/tmp`). Do not budget “40 s” until the Linux signer measures cold init. Abort import if warmup exceeds ~50 s. Keep functions few and fat so LLVM fits.

Zip root (platform does `import agent`):

```
agent.py              # get_move, init warmup, ponder stop-join, firewall
board_nb.py           # 12 bitboards, occ, castle, ep, fifty, zobrist make/unmake
movegen_nb.py         # leaper tables, ray sliders (magics later), in-check
search_nb.py          # ID, AB/PVS, qsearch, RFP, NMP, LMR, IIR
eval_nb.py            # incremental PeSTO + cheap terms
tt_nb.py              # numpy packed TT
time_nb.py            # soft/hard/panic
tables_nb.py          # PST, zobrist keys, (later) magics — generated once, shipped
history.py            # game FEN/zobrist chain, anti-rep, 300-ply counter
syzygy/               # optional 3–4 man *.rtbw *.rtbz
# no weights/ unless SPRT-green net
# no torch import
```

`make zip` must put `agent.py` at archive root. The official packager only auto-includes `*.py` at cwd plus a `weights/` dir — we will extend it to include `syzygy/` and `tables` artifacts.

---

## 4. Search — the engine

Order of implementation is the freeze-week cut, then leftovers. If time runs out, the zip is last-good: legal, timed, firewalled, draw-aware — never a half-integrated D/F/G.

### Brick A — correctness

- FEN → internal position → UCI roundtrip
- **Ray-loop bitboards + precomputed leapers.** Magics are not a correctness dependency.
- Perft vs `python-chess` on startpos, Kiwipete, CPW 3–6, and 20 random FENs, depths 1–5
- Encoded moves packed in one int: from, to, promo, capture, EP, castle, double-push
- Make/unmake restores hash, castle, EP, fifty exactly

**Status (3 Sep):** Python `board_nb.py` / `movegen_nb.py` / `tables_nb.py` are perft-exact. Brick B searches on this generator. `@njit` waits on the Linux 3.12 signer.

No search feature until perft is exact. If perft is red, the living zip is **python-chess ID+AB**, not a buggy Numba generator. The **first platform upload** is still a legal mover even if A is unfinished — packaging must be known this week.

### Brick B — a move that never flags, and does not auto-draw a win (**first real search zip**)

- Iterative deepening, depth 1 → N. Keep last completed iteration. Depth-1 legal fallback exists before search.
- Fail-soft negamax, **one thread on our clock**
- Time (milliseconds; increment after we return):
  `moves_left = clamp(expected, 1, 40)` — floor 1 is effective only when ply ≥ 262; early/midgame still clamps to the same 20–40 band as the old floor of 20. Do not use FEN fullmove as gospel.
  `soft = (time_left_ms - 1500) / moves_left + 0.5 * 500`
  `hard = min(time_left_ms - 400, 2 * soft)`
  Never start an iteration unless remaining > 200 ms. Check the clock inside the loop.
- Panic: `<250 ms` → TT move if legal, else first legal. **No qsearch in panic.**
- Root python-chess firewall: if internal best is illegal, any legal UCI.
- Underpromotion generated (q, r, b, n)
- **Referee draws live here, not in a later brick:**
  - Maintain `board._transposition_key()` for every served FEN and after each legal push of our UCI. Do not infer opponent UCI from FEN deltas.
  - In search, repetition = 0.
  - Winning: do not allow a second occurrence of a key (a later legal return is an auto-claim before `get_move`).
  - Winning and `halfmove >= 90`: only zeroing moves (pawn/capture). At 99 a single quiet legal move lets the referee draw without calling us.
  - 300-ply: ply = this game’s half-moves from the start FEN (`move_stack` analogue). If `300 - ply <= 16`, search with kingless P1 N3 B3 R5 Q9, age/clear TT. Do not use FEN `fullmove`.

This brick may be stupid. It may not die. It must not gift a 3fold. The first **upload** may still be a legal random/greedy so the dashboard works.

**Status (3 Sep):** `get_move` runs ID + fail-soft AB on the Brick A generator, vanilla PeSTO (kingless material in the last 16 plies), middlegame clock, python-chess root firewall, and `history.py` `_transposition_key()` / fifty-zero / no-second-occurrence when winning. No qsearch, no TT. Panic is first legal (filtered). `python -m lab.test_b` is the Brick B gate.

### Brick C — qsearch, TT, ordering

- Qsearch: stand-pat only if **not in check**. If in check: all legal evasions, no stand-pat. Captures+promos otherwise. Delta prune, MVV-LVA, simple SEE skip SEE<0. Checks-as-captures off until nps is measured.
- TT: **64 MB** (`2^22` × 16 B) only if RSS after JIT allows it. Never 1 GB. Never import torch.
- Entry: key, move, depth, flag (exact/lower/upper), score, age. **Ply-adjusted mates.**
- Persist TT across our moves. Do not clear on a later ponder miss (ponder is not in the freeze zip).
- Hash move, two killers/ply, history `[piece][to] += depth*depth`
- Aspiration ±25 cp, one fail re-search, then full window. No 5-window loop.

TT surviving the game is free Elo the protocol already gave us.

**Status (3 Sep):** Packed 64 MB `tt_nb.py` (2^22 × 16 B, ply-adjusted mates, persists across our moves). Qsearch stand-pat only if not in check; evasions if in check; delta + MVV-LVA + SEE<0 skip. Hash move, two killers, history. Aspiration ±25, one fail then full window. Panic: TT move if legal, else first legal — no qsearch. Skip TT in the 300-ply adjudication window. `python -m lab.test_c` plus `lab.test_b`.

### Brick D — opportunistic, not freeze-critical

Only if C is green and flag-rate is 0. Skip LMR unless one real SPRT exists.

- **RFP before LMR** (not PV, not check, depth ≤ 6, `eval >= beta + 80*depth` → cut). **Improving gate** (measured brick): only when `static_eval >= EVAL_STACK[ply-2]` (or ply < 2). Off in check and in the adjudication window.
- Forward futility on quiets, depth ≤ 2
- NMP: not in check, not PV, depth ≥ 3, **has non-pawn non-king material**, `R = 2 + depth//6`. Same **improving** gate as RFP. No verification search.
- PVS only after hash move + killers exist
- LMR: quiet, not check, index ≥ 3, depth ≥ 3, not killer. **SPRT vs no-LMR before it stays.** Premature LMR with PeSTO ordering is an Elo loss.
- Simple SEE (swap-off, no X-rays)
- Check extension +1 once, **capped**; `ply < 128` is not a licence to explode
- **IIR not IID**: depth ≥ 4 and no TT move → search `depth-1`
- Main-search SEE prune (measured): non-PV, not in check, captures/promos, depth ≤ 6, not hash move, `see_nb < 0`

Skip: singular, ProbCut, continuation/countermove history, razoring, LMP, magics finder, dynamic ID clock (`soft_budget` / `early_stop_ok`) unless a dedicated soak is green.

### Brick E — leftover contest physics (most of this is now Brick B)

**Pondering: not in the freeze zip.** TT across our moves is enough. A nogil search will not die in `join(50ms)`.

**Anti-repetition / fifty / 300-ply:** implemented in B. Do not leave them “for later.”

**Contempt.** One constant per zip if we ever measure it. Default 0.

**Panic.** As Brick B. Survival.

### Brick F — endgame (not this freeze week)

Skip Syzygy in the freeze zip. Default packager drops subdirs. Student games die in tactics; KQK is search. If later: `du` a closed 3–4 man WDL+DTZ set, `--include`, skip positions with castling rights, wrap every probe, never crash.

---

## 5. Evaluation — PeSTO first, then one extra layer

Shipped eval is **vanilla PeSTO** (Ronald Friederich / RofChade): tapered MG/EG material + PST. Incremental on make/unmake. Do not bolt untuned pawn/king terms onto an already-Texel-tuned PST this week (double-count). Bishop pair (`BP_MG=25`, `BP_EG=40`, exclusive) ships only when **Python `eval_nb.pesto` and Numba `pesto_nb` match**; no bonus under adjudication. Tempo ~10 cp is the one cheap extra that is usually harmless.

**Texel:** do not retune published PSTs. Extra terms are not freeze work.

**Brick G net — out this week.** Not because 1-core physics forbids a 768→32→1 or a tiny ONNX eval (a rival may have one). Because we have no labels, no time, and no SPRT. Default: out.

A weaker eval at the same depth is a gift to the opponent. A CNN at 50–400 evals/s is a tactical child of Brick B.

---

## 6. Replica environment — fight on our terrain

The platform harness is already public (`advitrocks9/aichessathon-starter/harness`). We treat it as **source of truth** and wrap it, we do not “improve” it.

### 6.1 Official referee, wrapped not “improved”

Keep their files untouched (`harness/rules.py`, `referee.py`, `runner.py`, `sandbox.py`). This is protocol-identical to the **published starter**, not bit-identical to the unpublished contest image/CPU.

Live `referee.py` loop (3 Sep):

1. `board.outcome(claim_draw=True)` — draw can happen **before** `get_move`
2. `len(board.move_stack) >= 300` — ply cap of **this** game from the curated FEN
3. `agent.move(fen, int(clock))` — wall time, then `clock < 0` is a flag
4. increment added **after** a legal push

Do not call a one-container `--cpus=1` match a replica of two dedicated cores.

- `INIT_BUDGET_S = 60`
- `BASE_MS = 120_000`, `INCREMENT_MS = 500`
- `PLY_CAP = 300`
- `STDOUT_CAP = 4096`
- `WATCHDOG_GRACE_MS = 500`
- material adjudication without king
- `claim_draw=True`

Our additions live in `lab/`:

- `lab/docker/` — image with Python 3.12 and the five pinned packages, `nproc=1`, `memory=2g`, no network, `/tmp` 256m
- `lab/gauntlet.py` — N games, colour-alternating, pentanomial, optional SPRT, JSONL log. **Measurement, not training.** Does not write PeSTO. `--hours` is the overnight flag-rate job on the host after collectors pause; not inside the 2 GB signer container (that envelope is one agent).
- `lab/openings.py` + `lab/openings.fen` — a **private** set of 200 balanced FENs (8–12 ply of reasonable play, |PeSTO| small). Rated games use unpublished curated positions; testing only on startpos is how people get surprised. Regen: `python -m lab.openings --regen`.
- `lab/fuzz.py` — promotions, EP, castling both sides, checks, mates, stalemates, fifty, threefold, KPK, insufficient material
- `lab/bench.py` — nps, depth, time-to-move histograms, flag rate
- `lab/gate.py` — CI: perft + 2 smoke games + fuzz + “no flags in 50 fast games”

Windows (this laptop): `make play` / `make arena` for the inner loop. **Pin process affinity to one core** (`ProcessorAffinity = 1`) or nps is a lie on a 10-core Snapdragon.

Linux signer: one **agent** process at a time after collectors pause. Envelope for that process: `--cpus=1 --memory=2g --network=none --read-only --tmpfs /tmp:size=256m`. Use it for cold init, nps, and freeze zips. Do not run both colours under one `--cpus=1` and call the clocks real. **Never freeze a Windows-only zip.** Promote on: perft, flag-rate 0 on a short fast-TC set, 2-game real-TC smoke. At most one SPRT if the signer has room. `dist/last-good.zip` is sacred.

### 6.3 Replica daemon vs “training”

Two different jobs that share the word “uptime”:

| Job | Runs where | Needs contest image? | On this 4 GB box? |
|---|---|---|---|
| Identity smoke, nps, flag-rate, real-TC gauntlet | Replica container | Yes — that is the point | **Yes. This is the daemon.** |
| SPRT zip A vs zip B (self-play of *our* agent) | Replica or replica-shaped | Yes, or we lie to ourselves | Yes, **one** pair at a time, after internwatch/CRL pause |
| Stockfish eval labels / Texel | Host, leftover RAM, SF binary | **No** (SF is not in the image) | Only if replica still has slack |
| Torch / 768→32→1 SGD | Laptop or leftover host RAM | **No** — then SPRT the weights *in* the replica | Default off |

The replica is a wind tunnel. You do not build the car inside the tunnel. You put the car in and read the gauges.

### 6.2 Assets found on this machine

Inventory of 2 Sep 2026 (laptop sweep). Secrets are not stored in this repo.

**Laptop — not the contest machine.** Microsoft Surface Laptop 7th Edition, Snapdragon X1P64100 (10C ARM), 16 GB RAM, Qualcomm Adreno (no NVIDIA, no CUDA). Windows ARM64 + WSL2 aarch64. Default Python is **3.14**; contest is **3.12**. Local numba 0.66 / onnxruntime 1.27 on 3.14 — useful for syntax, **useless for freeze nps**. Disk C has ~26–28 GB free; do not dump self-play or 5-man Syzygy here. Docker CLI is not on PATH. Repo `.venv` is 3.14 + `chess==1.11.2` (Brick 0+A perft/smoke). No Stockfish, no `.nnue`, no tablebases, no Polyglot book, no prior chess-engine repo (GitHub: FiNdAlMkSkInDaL).

**VPS — Linux x86_64 Python 3.12 signer, ~4 GB.** Already running memory-heavy collectors. A 2 GB replica plus OS plus collectors OOMs. Pause collectors before the signer. No GPU. Ops patterns to copy (not product code): rsync + systemd, “signer is source of truth for zips.” Hostnames, IPs, usernames, and key comments do **not** belong in this file.

**VPS doctrine.** One-agent signer after collectors pause. No SGD in the contest-shaped container. No SF in that container. No username spray. vCPU count unconfirmed until a **console** inventory. A quiet UCL x86 Linux lab PC is an acceptable substitute signer.

Never freeze a Windows ARM zip. Every freeze candidate is packed and smoked on the Linux signer.

---

## 7. Pipelines — frictionless, gated, boring

### 7.1 Inner loop (minutes)

```
edit njit function
  → warmup still works
  → perft (must be exact)
  → make play vs baselines/minimax at 10s+0.1s
  → if crash or flag: do not continue
```

### 7.2 Measurement loop

```
change one thing
  → perft still exact
  → ~20 games flag=0 at 10s+0.1, mixed FENs
  → 2-game real-TC smoke on the signer
  → optional: ONE sprt this week if the signer can host it
  → promote only if flags stay 0
```

Two games tell you nothing about Elo. They tell you about crashes. We obey both facts.

### 7.3 Upload loop

```
Linux signer smoke (2 games, both colours, curated FEN)
  → fuzz
  → 50-game flag-rate = 0
  → upload
  → read validation log verbatim
  → if init/crash: rollback to last-good zip immediately
```

Keep `dist/last-good.zip` and `dist/candidate.zip`. Six uploads/day is a budget, not a target. Never upload an ungated zip. Sleep on a known-good.

### 7.4 When uploads close

The zip that plays Swiss is **last-good**, not last-pushed. If A+B+C is unfinished, we freeze the last legal never-flag zip, not a half-integrated D.

### 7.5 Data / training (out this freeze week)

No labels, no net, no Texel-on-PeSTO. The signer’s job is smoke and nps, not SGD. Revisit only if A+B+C is green with flag=0 and leftover host RAM exists.

---

## 8. 50 MB budget

| Item | Budget | Notes |
|---|---|---|
| Python source | < 1 MB | readable; we explain it at the final |
| Zobrist + PST | 2–8 MB | generate once, ship arrays |
| Slack | rest | no TB/net/magics in the freeze zip |

The packager warns at 50,000,000 bytes. Stay under 40 MB so unzipped slack exists.

---

## 9. Freeze-week cut (not a cathedral)

Contest freeze is their clock. The zip is A+B+C or the last legal never-flag upload.

```
Brick 0  clone starter + legal get_move + package smoke
         first platform zip = legal mover (learn dashboard/init)
   │
   ▼
Brick A  perft-exact rays  — if red, python-chess AB is the searcher
   │
   ▼
Brick B  ID+AB + clock + firewall + auto-claim 3fold/50 + 300-ply count
   │
   ▼
Brick C  qsearch (evasions if in check) + TT + ply-adjusted mates + ordering
   │
   ├─ D opportunistic (RFP/NMP/SEE; no LMR without one SPRT)
   ├─ no ponder, no magics, no TB, no net, no Texel
   ▼
Linux signer  cold init + nps + freeze zip  (required before freeze-candidate)
```

Brick 0 when we go: clone starter; pin referee untouched; legal `get_move`; Python 3.12 for agent runs; pack with `agent.py` at zip root. Register before first upload. Console inventory when we can — does not block clone. Not: train, magics, torch import, SSH spray, host strings in git.

London: walk through this file. Knockout uses the frozen zip unless they reveal a new constraint; if they do, change the **minimum** surface (time manager), not the searcher. Confirm the London invite by reply.

---

## 10. Module-level state (the protocol is a feature)

Persists for one game, dies between games:

- TT (do not clear between our moves)
- killer / history tables
- `_transposition_key()` chain: start FEN + every served FEN + after each of our legal pushes
- start FEN + ply count of **this** game (not FEN fullmove)
- our colour (side-to-move of first FEN)
- node counters for logging (validation log only)

`/tmp` is empty every game. Do not cache magics there across games; ship them.

Two games may run at once in two containers. No shared disk. Fine.

---

## 11. Failure budget

A Swiss game is lost for free by (ranked by how students actually die):

1. Flag (greedy soft bound; JIT on first move; qsearch explosion; panic qsearch)
2. Illegal UCI. Root firewall mandatory
3. Crash on EP / castle / underpromo / empty legal list / OOB TT move. Perft first
4. Init timeout (`import torch`; too many micro-functions). Fail import before 60 s rather than flag game 1
5. Output > 4 KB / `chess.py` shadowing
6. OOM from a huge TT
7. Auto-claim 3fold/50 **before get_move** when winning (any legal completing move / quiet at 99)
8. 300-ply using FEN fullmove, or switching eval without ageing the TT
9. Stand-pat in check in qsearch

Gate every upload against 1–6. Draw logic is in B.

---

## 12. Wacky, legal, on-purpose

Ideas we *will* use if cheap:

- **Adjudication eval** in the last 16 plies of **this** game’s stack, same eval in search, TT aged.
- **Move-count time scaling** with a 400 ms hard margin, not 80 ms.
- **Avoid second occurrences when winning** (auto-claim is wider than filtering our intended move).

Ideas we will not spend a freeze-week brick on:

- Ponder
- Polyglot
- Ensemble / MCTS / Lazy SMP / magic finder / IID / Texel-on-PeSTO / torch import
- Syzygy this week
- Contempt grids

---

## 13. Team split

If solo: one brain, DAG above, VPS as freeze signer (not extra compute).

If two/three (max):

| Seat | Owns |
|---|---|
| Search | ray bitboard, ID/AB, TT, time, stop-join ponder |
| Eval / data | PeSTO extra terms (not PST retune), optional net, syzygy packaging |
| Ops | replica Docker, SPRT, uploads, validation logs, fuzz, freeze discipline |

Nobody merges to `main` without `lab/gate.py` green. Nobody uploads except Ops.

---

## 14. London walkthrough script

They will ask how it was built. Answer in this order:

1. We wrapped their referee and tested claim_draw / 300-ply stack, not startpos.
2. We JITed a ray-bitboard search because `python-chess` in the loop cannot win.
3. Eval is published PeSTO. We did not retune the tables on a toy set.
4. We play *their* auto-claim draws and 300-ply scoring. We did not ponder in the freeze zip.
5. The Swiss zip is last-good. Flag = 0.

That is a finalist story that survives a reading of the source.

---

## 15. Immediate next brick (wait for explicit go)

When we start Brick 0:

1. Register before the first upload.
2. Clone official starter; pin their referee untouched.
3. Python 3.12 for agent runs. Legal `get_move` that never throws. Pack `agent.py` at zip root.
4. First platform zip: legal mover, learn the validation log. That is `last-good`.
5. Then A (perft). Then B (search + draw logic). Then C. Linux signer before anything is called a freeze candidate.

Do not train a net. Do not write a magic finder. Do not SSH-spray. Do not put host logins in git. Put a legal mover on the platform, then walk A→B→C.
