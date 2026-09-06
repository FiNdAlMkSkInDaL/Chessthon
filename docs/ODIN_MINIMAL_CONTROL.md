# Minimal Storm control for Odin release validation

`storm_rules600_release_control/` is a separately named test opponent built
directly from the exact Storm v4/r2 archive with SHA-256
`15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c`.
It does not replace Storm, Odin, or the earlier `storm_rules600_control/`.
The earlier control already contains most Odin search changes and is unsuitable
for isolating the complete successor's gains beyond the new cap repair.

Run `lab/odin/build_release_control.py` to reproduce the source. The builder
verifies the input archive hash, writes only this new directory, and emits
`lab/odin/release-control-source.manifest.json` and the exact newline-normalized
diff `lab/odin/release-control.diff`. Six modules remain byte-identical to Storm:
`agent.py`, `bitops_nb.py`, `board_nb.py`, `movegen_nb.py`, `tables_nb.py` and
`tt_nb.py`. The other changes are:

- `history.py` obtains absolute ply from every served FEN using `board.ply()`
  and never requests the obsolete material-adjudication mode.
- `eval_nb.py` and `core_nb.py` always use Storm's unchanged PeSTO evaluation.
- `storm_clock.py` and legacy `time_nb.py` change only the cap constant from
  300 to 600; the original clock allocation and controller are retained.
- Native and fallback search carry the remaining cap through real legal
  edges and score its terminal state as a draw after mate precedence. Null
  edges do not consume the cap; native null also stops advancing rule 50.
- Native real-history capacity is `history length + MAX_PLY + 8`.
- Cap-sensitive TT score identity is separated near the reachable 96-ply cap
  horizon. Beyond that horizon the original position key is retained, so
  ordinary move ordering, TT reuse and panic hints behave as Storm did.
- At the cap and maximum recursive ply, native checking uses small local
  scratch arrays instead of indexing past the preallocated search stack.

Storm's original capture SEE, LMR, null pruning, move ordering, aspiration
retries, repeated-position search heuristic, raw-EP identity and static
winning-root filtering are intentionally retained. In particular, the old
root filter can still reject useful drawing defences or quiet moves; removing
that filter is part of Odin's measured change. This control is a minimally
updated version of the old opponent, not a reference implementation of all
chess rules or a claim that every inherited search heuristic is correct.

The native callable retains Storm's original signature:
`search_root(pos, packed_root, hard_ms, soft_ms, adjudicate, game_zkeys)`.
It derives absolute ply directly from the packed facade's FEN fullmove and side.
The public `agent.get_move` interface is unchanged. The supplied adjudication
argument is preserved for callers but the obsolete mode is ignored.

Five isolated lightweight tests pass in `lab/odin/test_release_control.py`:
preserved source/functions, absolute FEN ply, cap draw/mate/maximum depth,
cap TT identity, and legal-versus-null native cap argument flow. Native cold
import, compiled terminal/state/buffer/deadline checks, packaging and matches
remain the release owner's required gates. This directory is not an approved
submission archive.
