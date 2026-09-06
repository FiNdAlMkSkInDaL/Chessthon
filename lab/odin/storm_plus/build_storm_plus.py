"""Bounded port onto the exact native, minimally rule-corrected Storm control."""
from __future__ import annotations
import ast
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = ROOT / "lab/odin/native_release/control-r1/candidate-linux-x86.zip"
EXPECTED = "35c6a33fed2e81acead145de53639ce516b1d24a6701a89a8c5fff81a582baf1"
SOURCE = ROOT / "odin_storm_plus"
PORT = ROOT / "odin"


def function_text(source, name):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    start = min([node.lineno] + [n.lineno for n in node.decorator_list]) - 1
    return "".join(source.splitlines(keepends=True)[start:node.end_lineno])


def replace_function(source, name, replacement):
    old = function_text(source, name)
    assert source.count(old) == 1
    return source.replace(old, replacement)


WARMUP = '''def warmup() -> bool:
    """Compile the exact original Storm root signature before reporting ready."""
    global NUMBA_READY, WARMUP_S
    from board_nb import START_FEN, from_fen
    from movegen_nb import generate_legal

    began = time.perf_counter()
    NUMBA_READY = False
    pos = from_fen(START_FEN)
    _ = perft_pos(pos, 2)
    packed = generate_legal(pos)
    bb, mb, st = pack_pos(pos)
    root = np.array(packed, dtype=np.int32)
    hist = np.empty(MAX_PLY + 8, dtype=np.uint64)
    undos = np.zeros((MAX_PLY, 7), dtype=np.uint64)
    stacks = np.zeros((MAX_PLY, MAX_MOVES), dtype=np.int32)
    scratches = np.zeros((MAX_PLY, MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(2, dtype=np.int64)
    aborted = np.zeros(1, dtype=np.int32)
    nodes[0], nodes[1] = 1024, 1
    if not check_clock(nodes, 10**15, True, aborted) or not aborted[0]:
        raise RuntimeError("Native monotonic-clock warmup did not abort")
    nodes.fill(0)
    aborted.fill(0)
    # Finite depth-one start-position search; compilation has no live deadline.
    _ = root_search_nb(
        bb, mb, st, root, len(packed), 1, hist, 0, int(root[0]),
        -INF, INF, 0, 600, 10**15, undos, stacks, scratches,
        TT_KEY, TT_MOVE, TT_SCORE, TT_DEPTH, TT_GEN, TT_AGE,
        KILLERS, HISTORY, nodes, aborted,
    )
    if not root_search_nb.nopython_signatures or aborted[0]:
        raise RuntimeError("Native root search was not compiled during import")
    WARMUP_S = time.perf_counter() - began
    NUMBA_READY = True
    return NUMBA_READY
'''


def main():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == EXPECTED
    with zipfile.ZipFile(BASE) as archive:
        old = {name: archive.read(name) for name in archive.namelist()}
    assert len(old) == 12
    outputs = dict(old)
    core = old["core_nb.py"].decode("utf-8").replace("\r\n", "\n")
    odin_core = (PORT / "core_nb.py").read_text(encoding="utf-8")
    for name in ("make_nb", "make_null", "see_nb"):
        core = replace_function(core, name, function_text(odin_core, name))
    for name, before in (("ep_hashable_nb", "put"), ("legal_lva_see_nb", "see_nb")):
        anchor = function_text(core, before)
        core = core.replace(anchor, function_text(odin_core, name) + "\n\n" + anchor)
    assert core.count("            make_null(st, undos[ply])") == 1
    core = core.replace("            make_null(st, undos[ply])", "            make_null(bb, mb, st, undos[ply])")
    core = replace_function(core, "warmup", WARMUP)
    outputs["core_nb.py"] = core.encode("utf-8")
    outputs["board_nb.py"] = (PORT / "board_nb.py").read_bytes()
    search = old["search_nb.py"].decode("utf-8").replace("\r\n", "\n")
    search = replace_function(search, "see", function_text((PORT / "search_nb.py").read_text(encoding="utf-8"), "see"))
    outputs["search_nb.py"] = search.encode("utf-8")
    history = old["history.py"].decode("utf-8").replace("\r\n", "\n")
    history = replace_function(history, "filter_root_moves",
        function_text((PORT / "history.py").read_text(encoding="utf-8"), "filter_root_moves"))
    # The control intentionally retains a cycle-avoidance search heuristic;
    # do not claim exact referee threefold search in the all-legal root docstring.
    start = history.index("    \"\"\"All legal roots are searched.")
    end = history.index("    del board, winning, deadline", start)
    history = history[:start] + (
        '    """Keep every legal root, including drawing resources and quiet defences.\n\n'
        '    The inherited search treats a path cycle as a draw heuristic; this\n'
        '    is deliberately distinct from the referee claiming true threefold.\n'
        '    """\n') + history[end:]
    outputs["history.py"] = history.encode("utf-8")
    SOURCE.mkdir(exist_ok=True)
    for name, data in outputs.items():
        ast.parse(data.decode("utf-8-sig"))
        (SOURCE / name).write_bytes(data)
    diff = []
    for name in sorted(outputs):
        diff.extend(difflib.unified_diff(
            old[name].decode("utf-8-sig").replace("\r\n", "\n").splitlines(True),
            outputs[name].decode("utf-8-sig").replace("\r\n", "\n").splitlines(True),
            fromfile="native-control-r1/" + name, tofile="storm-plus/" + name))
    (HERE / "against-control-r1.patch").write_text("".join(diff), encoding="utf-8")
    snapshot = HERE / "odin-storm-plus-source.zip"
    with zipfile.ZipFile(snapshot, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(outputs.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 5, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    manifest = {"source_only_not_release": True, "base_zip_sha256": EXPECTED,
                "source_zip_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                "files": [{"name": name, "sha256": hashlib.sha256(data).hexdigest(),
                           "bytes": len(data), "unchanged_from_control": data == old[name]}
                          for name, data in sorted(outputs.items())]}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
