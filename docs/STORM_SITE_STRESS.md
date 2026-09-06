# Supplementary site-opening stress test

Storm r2 scored **one win and three draws, with no losses**, against signed v3
in four games at 120 seconds plus 0.5 seconds per move. Neither engine had an
operational failure. This is a separate Windows stress test on two selected
historical starts; its games are excluded from the native holdout confidence
interval and do not establish Elo or leaderboard strength.

The selection was fixed before play: indices 8 and 10 from
`lab/storm/site_openings.fen`, corresponding to day-one rounds 9 and 12.
These test already-castled and substantially developed positions that the local
synthetic opening corpus underrepresents. Both colours were played for each
start. Selection details and original file hashes are in
`lab/storm/site_stress_selection.json`.

| Game | Historical start | Storm colour | Result | Termination | Game plies | Storm clock left | V3 clock left |
|---|---|---|---|---|---:|---:|---:|
| 1 | R9, both kings castled | White | Draw | Fifty-move claim | 293 | 1.831 s | 2.714 s |
| 2 | R9, both kings castled | Black | Win | Checkmate | 95 | 7.074 s | 25.456 s |
| 3 | R12, developed position | White | Draw | Threefold claim | 65 | 37.546 s | 35.592 s |
| 4 | R12, developed position | Black | Draw | Threefold claim | 87 | 10.077 s | 24.498 s |

Storm averaged 14.132 seconds remaining versus v3's 22.065 seconds. Its longest
move took 10.109 seconds. Time used for its first 20 decisions ranged from
60.862 to 69.253 seconds; v3 ranged from 73.841 to 75.986 seconds. Clock figures
come from the referee-facing move timings, including the increment after each
successful move, rather than Storm's search-only telemetry.

The first draw ended with Storm's rook and bishop against a rook, seven plies
before the 300-ply adjudication limit. That material advantage does not prove
the position was won. In the third game Storm had two extra pawns, but v3's
queen checks repeated with rook blocks; Storm's final completed search scores
were zero. The fourth game also ended in repeated checks with final search
scores of zero. These games show remaining conversion and king-safety questions,
not verified winning positions being thrown away.

The archives were immutable throughout:

- Storm r2: `dist/storm-r2-linux-x86.zip`, SHA-256
  `15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c`.
- V3: `dist/agent-v3-linux-x86.zip`, SHA-256
  `3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408`.

The untouched referee ran through `lab.laptop_match` on Python 3.12.10, with
fresh exact archive extractions, CPUs 8 and 9, and verified 2 GiB Windows Job
Object limits. Those CPUs were used only after the earlier evaluation screen
and its children exited. Both players had original and effective
`NUMBA_READY=True` in all four games; the laptop readiness shim applied no
override. Post-game archive and extraction checks were clean.

Local initialization varied materially: Storm took 38.250–85.531 seconds and
v3 took 31.672–75.250 seconds. All were below the live 90-second limit, but the
worst timings exceeded the conservative signer target. This Windows run is
not native Linux readiness evidence. The laptop has an ARM host and x64 Python,
writable private extractions, no network namespace, and no aggregate 256 MiB
temporary filesystem quota. Its memory sampler observed the venv launcher
instead of the actual engine PID, so those RSS figures are not presented as
engine memory use; Job Object enforcement was independently verified.

Raw log: `lab/storm/site_stress_r2_vs_v3.jsonl`. Detailed results and readiness
evidence: `lab/storm/site_stress_r2_vs_v3_report.json`. All four replay-verified
PGNs with per-move clock annotations: `lab/storm/site_stress_r2_vs_v3.pgn`.
Regenerate the exports with `python -m lab.storm.report_site_stress`.
