# Odin implementation status — 5 September 2026

**Released 6 September:** the exact Odin v6 Linux ZIP is the signer archive
(not in git), after all 112 games passed the frozen promotion gate. Current
source: `odin_v6/`. See [ODIN_V6_RELEASE_REPORT.md](ODIN_V6_RELEASE_REPORT.md)
and [ODIN_DAY3_REVIEW.md](ODIN_DAY3_REVIEW.md). Older status text below is
retained as history, not the current release instruction.

**Latest work:** Odin v6's architectural speedup is packed, natively gated and
in a new 112-game overnight comparison against released v5. Read
[ODIN_V6_MORNING_REVIEW.md](ODIN_V6_MORNING_REVIEW.md) before continuing.
the signer archive (not in git) remains v5 while that comparison runs.

**Superseded implementation snapshot.** Continued native testing found that
the exact-history foundation below was weaker than Storm. Active release work,
candidate hashes, jobs and pending gates are recorded in
[ODIN_RELEASE_PROGRESS.md](ODIN_RELEASE_PROGRESS.md). The current prepared
source is `odin_submission/`, based on the faster Storm search with original
fitted positional evaluation. the signer archive (not in git) is now Odin R10 after the
user-authorized expedited16-game decision (9W/2D/5L, zero operational faults).
The original112-game confidence plan was cancelled, not passed. Read the
progress document and expedited release report before continuing.

## Preservation

The four official Storm v4/r2 archives remain byte-identical at
`15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c`.
Development is confined to `odin/`; the historical `harness/` is untouched.
`storm_rules600_control/` is the separately named pre-evaluation
rules/search-corrected control snapshot. It is not the official Storm release.

## Implemented in Odin

- Models the current referee's absolute 600-ply cap from FEN `board.ply()`;
  legal search edges, not null moves, consume it. Normal mate/stalemate
  outcome is checked before the cap draw.
- Removes Storm's obsolete 300-ply material mode, 300-ply clock collapse,
  fixed 512-entry history allocation, static +80 root deletion, and raw-EP
  repetition identity.
- Uses legal canonical EP hashing, exact long real-history allocation,
  threefold/rule-50 claim search, context-valid TT score keys, legal SEE, and
  a sparse queenless null-move fail-high verification search.
- Adds one-sided aspiration retry, returned-move retry ordering, root-work
  accounting, and compact O5 telemetry with in-memory bounds/retry/stop data.

## Current immutable source snapshot

`lab/odin/odin-rules-search-source.zip` is a source-only, audited local
snapshot; it is **not** a Linux release and must not be uploaded.

- SHA-256: `64b9084d58e0f292ee7c61a6f09c2bcae31a2a2cc8bca544f18131018ce22dc6`
- 12 Python modules; 146,961 uncompressed bytes
- Manifest: `lab/odin/odin-rules-search-source.manifest.json`

The local extracted bytes passed the current pinned starter's 600-ply sandbox
and the source operational gate. Windows 3.12 cold imports measured 63.522 s
(extracted gate) and 64.384 s (pinned sandbox); this is below the live 90 s
limit but is not a Linux performance result.

## Tests completed

- Current pinned-referee cap, mate precedence, FEN absolute-ply, and canonical
  legal/pinned/impossible EP tests pass.
- Native cap, mate precedence, long history, SEE fixtures, TT context,
  null restoration, sparse-null guard and root-telemetry tests pass.
- Clock tests cover the 600-ply horizon and root-effort/retry controller.
- Diagnostics reconstruct all 37 history-complete roots and 1,012 legal roots;
  all opening-165 tablebase drawing roots remain searchable.
- Exact extracted source passed local native deadline/firewall and pinned
  protocol checks.

## Fitted-evaluation experiment (not release-enabled)

`lab/odin/training/` contains a reproducible offline experiment, never runtime
position data: 19,974 non-mate labels from a 20,000-position public PGN corpus
of Carlsen/Kasparov/Anand/Karpov/Tal/Fischer games. First-eight-ply opening
families were split before fitting (15,100 train / 4,874 validation). Stockfish
19 supplied single-thread 2,000-node labels.

The tapered Huber ridge fit (`ridge-fit-sf19-n2000.json`) improves held-out
validation error from 275.292 to 273.104 cp MAE and from 426.690 to 421.911 cp
RMSE. Its independent feature-geometry and validation tests pass. A native
implementation was deliberately removed from the search evaluator after a
fresh local import measured 132.247 s, beyond the live 90-second init limit.
The fit is evidence for a future smaller implementation, not a claimed Odin
strength gain.

## Promotion blockers

Do not name the snapshot `Odin-v5-linux-x86.zip` or upload it yet.

1. Run the exact snapshot on the established Linux x86-64 signer under the
   1-core/2-GiB gate and build its Linux archive/manifest. No signer alias is
   configured locally; connection details were not guessed or read from
   private terminal history.
2. Freeze any final bytes, then run the predeclared 40-pair/80-game current
   referee holdout versus `storm_rules600_control/` and the separate 16-pair
   original-Storm guard. Neither exists yet, so no strength or promotion claim
   is justified.
3. Keep the positional experiment disabled until a much smaller native design
   passes cold-init, native cost, exact reference symmetry and fresh-game
   gates.
