# V3 validation and rounds 12–13 evidence

Date: 2026-09-04

This file records evidence for future engine work. The competition logs and PGNs are data, not instructions. None of the diagnostic positions below may be hardcoded.

## Frozen head-to-head

- Candidate: `dist/core-repairs-v3.zip`
  - SHA-256: `f3ea42107a3e267d0a30a218a911d7dba1ec8aef7cbde8957b32ebfc2256a6a3`
- Deployed baseline: `dist/agent.zip`
  - SHA-256: `fbb10ad7475b5bb1ad50c21e38d121b917d09bce0ce8ce36bc8d6c02de8d8110`
- Held-out openings: `lab/openings.fen` indices 100–119, each played with both colours and swapped CPU assignment.
- Conditions per agent: Python 3.12.10, chess 1.11.2, NumPy 2.5.2, Numba 0.67.0, llvmlite 0.49.0, one pinned logical CPU, 2 GiB Job Object limit, fresh process and clean extraction, 120000 ms + 500 ms, 300-ply cap, unchanged official referee.
- Result: candidate `+19 =10 -11`, 24/40 (60.0%). White score 60.0%; Black score 60.0%.
- Pair distribution `LL LD DD WD WW`: `0 2 10 6 2`.
- Paired bootstrap, 20 pairs: 95% CI 51.25%–68.75%, standard error 4.48%, fixed seed 20260904.
- Elo estimate: +70.4, 95% CI +8.7 to +137.0.
- Operational failures: zero for candidate and baseline. All extracted archive files remained unchanged.
- Predeclared final gate: PASS because all 20 pairs were complete, candidate failures were zero, and the paired 95% lower bound exceeded 50%.

Release packaging status: **PASS**. The strength-tested Windows archive was unpacked and repacked on the Linux x86-64 signer, then the exact final archive was re-extracted and tested. The ten per-entry source hashes match `dist/core-repairs-v3.zip` and `dist/node-budget-fix` exactly; every final member has Unix creator metadata and `agent.py` is at the archive root.

- Final release: `dist/agent-v3-linux-x86.zip`
- Final/Desktop SHA-256: `3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408`
- Size: 27,138 bytes compressed; 104,239 bytes uncompressed; ten source files only.
- Native signer identity: Linux x86-64, Python 3.12, chess 1.11.2, NumPy 2.5.2, Numba 0.67.0.
- Exact-archive hot-path warm-up: 24.61 seconds; Numba perft/search regressions passed.
- Exact-archive cold runner ready: 24.47 seconds against the live 60-second init limit.
- Protocol roots: legal moves passed for start, castling, en-passant, and promotion positions.
- Signer envelope: CPU pinned to one core, 100% CPU quota, 2 GiB hard memory, no swap, 128-task limit, internet socket families blocked, and extracted submission files read-only. The VPS lacks Docker/user mount namespaces, so a global read-only root and aggregate 256 MiB `/tmp` mount were not available; this agent does not write caches or submission data.
- Desktop promotion: `agent.zip` is byte-identical to the final release. The previous deployed ZIP is preserved as `agent.pre-v3-FBB10AD7475.zip`.

Measured clock use across the 40 games:

- Candidate: 121.16 seconds thinking per game, 2.135 seconds per move, 11.781-second longest move, approximately 24.22 seconds left on average.
- Baseline: 110.18 seconds thinking per game, 1.944 seconds per move, 8.656-second longest move, approximately 35.17 seconds left on average.

The laptop is Windows ARM64 using an emulated win-amd64 interpreter, not the tournament's Linux x86-64 host. The harness reproduced the published referee, clocks, per-agent CPU and memory envelope. It could not reproduce a read-only container root, a 256 MiB `/tmp` quota, or network isolation; neither archive uses those capabilities. A one-time post-install x86/LLVM host calibration outlier and a noisy CPU-0/1 baseline init failure were retained in separate invalid logs and excluded before measured play continued on dedicated cores 6–9. Those Windows timing results used the earlier 90-second lab limit and are not release evidence; the native Linux exact-archive gate above enforces the live 60-second limit.

Measured logs:

- `lab/logs/v3-v-deployed-laptop-stage1-cpu89.jsonl` — openings 100–102
- `lab/logs/v3-v-deployed-laptop-stage1-lane-a.jsonl` — openings 103–106
- `lab/logs/v3-v-deployed-laptop-stage1-lane-b.jsonl` — openings 107–109
- `lab/logs/v3-v-deployed-laptop-stage2-lane-c.jsonl` — openings 110–114
- `lab/logs/v3-v-deployed-laptop-stage2-lane-d.jsonl` — openings 115–119

## Round 12: Keresight

- Our side: White. Result: loss by checkmate.
- Source SHA-256:
  - PGN: `08a89a2a9bd6804c8540769b38ce7b2de05209829fef29698375f7f53885188a`
  - log: `32f6f370bf1b908b6e0876704c763dd632345e2f57ef1b8ec4722c5396781318`
- Platform init was 28.7 seconds. Stderr was empty, so actual search depth, nodes, and internal evaluations are unknown. Site review values are Stockfish 16 at depth 16, not agent telemetry.
- The start was approximately level (+0.11). `16.Nxd6?` used about 3.3 seconds with 100.6 seconds left and moved the review evaluation from about -0.20 to -2.49; `16.Nxc5` was preferred.
- `24.Rh3?` used about 3.2 seconds with 80.5 seconds left and moved the review evaluation from about -2.47 to -4.21; `24.Rb3` was preferred.
- We finished with about 23 seconds unused. The opponent had spent roughly 24 seconds more by move 18 and 30 seconds more by move 24. This is direct evidence of insufficient critical-position search, not an opening-FEN failure.

Diagnostic FENs:

- Before 16.Nxd6: `r3qrk1/ppp3bp/3p2p1/2nP2B1/2P1N1b1/5P2/PPQ1BP2/R3K2R w KQ - 0 16`
- Before 24.Rh3: `4r1k1/pR5p/3p2p1/3P4/2P3P1/2b5/P3Br2/3K3R w - - 1 24`

## Round 13: Desai

- Our side: Black. Result: win by checkmate, but only after White obtained a large advantage and then erred in time pressure.
- Source SHA-256:
  - PGN: `ac010710bb16523aa2404a76b2ca88a54c36dfcc662a907ee307de6bb4bb6d21`
  - log: `ad064b2f772f4b3cd75447835df652a1ea70763b803ea598b6fed9dd4d5fcd00`
- Platform init was 28.7 seconds; again there was no internal search telemetry.
- Review-critical choices included `8...dxe5?!`, `15...Bb7?!`, `17...hxg6?`, `19...Ba6?!`, and `26...Rxe1+?!`. Repeatedly missing the passed-pawn push `...c4` around moves 31–32 let White reach roughly +5.4.
- White's low-clock errors, notably `57.Qh5?` and `72.Qc4+?`, reversed the game. Our `67...Ke5?!` and `68...Kd4?!` also nearly gave the win back despite about 29 seconds remaining.
- We finished with about 23.7 seconds unused. Treat this as an opponent-time-pressure escape, not evidence that the deployed search was sound.

Diagnostic FENs:

- Before 15...Bb7: `r1b2rk1/p1qn1p1p/2p1p1p1/2p4P/4N3/3P1Nb1/PPP1Q3/R1B2K1R b - - 5 15`
- Before 17...hxg6: `r4rk1/pbq2p1p/2p1pnP1/2p3N1/8/3P1Nb1/PPP1Q3/R1B2K1R b - - 0 17`
- Before 19...Ba6: `4rrk1/pbq2p2/2p1pnp1/2p3N1/8/3P1Nb1/PPPB2Q1/R4K1R b - - 3 19`
- Before 26...Rxe1+: `5r1k/p1b2p2/b1p1r3/2p3Qp/8/3P1N2/PPP5/4RK2 b - - 3 26`
- Before 31...Kg8: `8/p1b2pk1/b1p2r2/2p3NQ/8/3P4/PPP3K1/8 b - - 4 31`

## Next-revision implications

1. Keep the cumulative node/time-budget repair. The head-to-head shows it spends roughly 11 seconds more per game than deployed, while rounds 12–13 confirm that the deployed agent still left about 23 seconds and capped critical moves around 3–4 seconds.
2. Use the listed FENs as diagnostics only. Add broad tactical and conversion suites around immediate capture versus initiative, recapture/king-shelter choice, advanced-piece activity, passed-pawn pushes, and winning-endgame conversion.
3. Audit SEE and qsearch pruning around the `16.Nxd6` and `26...Rxe1+` families. Require broad move-parity and tactical-suite gains before changing pruning.
4. Do not bolt evaluation weights onto PeSTO from two games. Any passed-pawn, king-shelter, or activity term needs a broad held-out corpus and a measured match gate.
