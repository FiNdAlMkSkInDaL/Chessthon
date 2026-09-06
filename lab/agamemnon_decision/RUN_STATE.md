# Current execution / continuation

The32 unique fits,6 snapshot reproductions,23 Linux probe executions and48
short development games are complete. No blend neighbour beat25%; no direct
blend match was warranted. `docs/AGAMEMNON_DECISION_RESULTS.md` records results.

Replay25 qualified at7W/6D/3L and passed exact-archive Linux native/protocol gates.
It is running24 independent full120s+0.5s games against unchanged Tempest r1.
Current VPS root (use the established authenticated SSH destination, never
guess logins): `$HOME/chess-sign-odin-20260905/agamemnon-confirm-replay25`.

- `agamemnon-confirm-a.service`: CPU0, six colour pairs.
- `agamemnon-confirm-b.service`: CPU1, six colour pairs.
- `agamemnon-confirm-audit.service`: waits for both, runs the strict current-rule
  source/resource/protocol/clock/replay audit, writes `confirmation24/COMPLETE.json`.
- Local exec session19458 waits for that marker, downloads all evidence and the
  unpromoted candidate, then runs `render_confirmation_status.py`.
  If the laptop/session stops, remote games/audit remain durable. Retrieve the
  completed evidence; do not restart games or repeat source packing.

Local evidence target:
`lab/agamemnon_decision/release-gates/replay25/confirmation24/`.
The local renderer writes `docs/AGAMEMNON_CONFIRMATION_RESULTS.md` and updates
the summary status in ENGINEERING and the decision report. If that file does
not yet exist, inspect the remote completion marker/services and local session.

Candidate archive SHA256:
`a72338865851743b0f50ce2796c20eb3c3cc88f66c2e91c83e970e83fa36b58c`.
Plan SHA256:
`fd0279a83a3ed6ebfa887dabbb2c3d282d7f811f0f80ca6149e59e9d48137a16`.
Baseline/Desktop Tempest SHA256:
`0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4`.

No automatic promotion or112-game follow-on. Target is>=55% score and paired95%
lower bound>50%, zero faults; a24-game clean positive only nominates the final
release-strength guard. Twelve confirmation families are now consumed. The320
sealed Lichess roots remain unopened. Neither candidate selection nor blend
tuning may use these new outcomes within this confirmation.
