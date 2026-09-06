"""Reproduce the minimal 600-ply Storm control from the immutable release ZIP.

No native import occurs here. The resulting directory is a test opponent, not
a submission candidate. Run this script before freezing any control archive.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "dist" / "agent-storm-v4-linux-x86.zip"
EXPECTED = "15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c"
DEST = ROOT / "storm_rules600_release_control"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError((source.count(old), old))
    return source.replace(old, new)


def add_cap_arguments(source: str, native: bool) -> str:
    """Insert arguments at AST-verified coordinates, preserving other source."""
    tree = ast.parse(source)
    names = ("qsearch_nb", "negamax_nb", "root_search_nb") if native else (
        "_qsearch", "_negamax", "_root_search")
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    edits = []

    def after(node: ast.AST, text: str) -> None:
        edits.append((offsets[node.end_lineno - 1] + node.end_col_offset, text))

    for name in names:
        params = funcs[name].args.args
        if native:
            anchor = next(arg for arg in params if arg.arg == "adjudicate")
        else:
            anchor = params[-1]
        after(anchor, ", cap_left")
    for owner in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
        for node in ast.walk(owner):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            callee = node.func.id
            if callee not in names or any(isinstance(arg, ast.Starred) for arg in node.args):
                continue
            if native:
                params = [a.arg for a in funcs[callee].args.args]
                idx = params.index("adjudicate")
                hlen = node.args[params.index("hlen")]
                legal_edge = isinstance(hlen, ast.Name) and hlen.id == "hlen2"
                cap = "cap_left - 1" if legal_edge else "cap_left"
                after(node.args[idx], ", " + cap)
            else:
                if owner.name == "qsearch_score":
                    cap = "600"
                elif owner.name in ("iterative_deepening", "_negamax") and callee in (
                    "_root_search", "_qsearch"):
                    cap = "cap_left"
                else:
                    cap = "cap_left - 1"
                after(node.args[-1], ", " + cap)
        if native and owner.name == "search_root":
            for node in ast.walk(owner):
                if isinstance(node, ast.Tuple):
                    for child in node.elts:
                        if isinstance(child, ast.Name) and child.id == "adj":
                            after(child, ", cap_left")
    for offset, text in sorted(edits, reverse=True):
        source = source[:offset] + text + source[offset:]
    return source


def native_control(source: str) -> str:
    source = add_cap_arguments(source, True)
    source = replace_once(source,
        "    if adjudicate:\n        return kingless_nb(bb, st)\n    return pesto_nb(bb, st, True)",
        "    # The current referee draws at its cap; retain the PeSTO evaluator.\n"
        "    return pesto_nb(bb, st, True)")
    source = replace_once(source, "    st[FIFTY] += np.uint64(1)\n    if us == 1:\n",
        "    # An artificial null edge cannot advance the real rule-50 clock.\n    if us == 1:\n")
    source = replace_once(source, "    hist = np.empty(512, dtype=np.uint64)\n    hlen = len(zkeys)",
        "    hlen = len(zkeys)\n    hist = np.empty(hlen + MAX_PLY + 8, dtype=np.uint64)")
    source = replace_once(source, "    adj = 1 if adjudicate else 0",
        "    adj = 0\n    cap_left = max(0, 600 - (2 * (int(pos.fullmove) - 1) + int(pos.side)))")
    # Retain old call surface, but disable the obsolete material/pruning mode.
    source = replace_once(source, "    start = time.perf_counter()\n    bb, mb, st = pack_pos(pos)",
        "    adjudicate = False\n    start = time.perf_counter()\n    bb, mb, st = pack_pos(pos)")
    terminal = (
        "    if cap_left <= 0:\n"
        "        checked_at_cap = in_check_nb(bb, st, np.int32(st[SIDE]))\n"
        "        cap_moves = np.empty(MAX_MOVES, dtype=np.int32) if ply >= MAX_PLY else stacks[ply]\n"
        "        cap_scratch = np.empty(MAX_MOVES, dtype=np.int32) if ply >= MAX_PLY else scratches[ply]\n"
        "        legal_at_cap = gen_legal(bb, mb, st, cap_moves, cap_scratch)\n"
        "        if legal_at_cap == 0 and checked_at_cap:\n"
        "            return np.int32(-MATE + ply)\n"
        "        return DRAW\n\n")
    anchor = "    if ply >= MAX_PLY:\n        return evaluate_nb(bb, st, adjudicate)\n"
    if source.count(anchor) != 2:
        raise ValueError("native max-ply anchors")
    source = source.replace(anchor, terminal + anchor)
    # Cap-sensitive scores get a separate key only where the 96-ply native
    # horizon can reach the cap. Ordinary middlegame TT behavior stays intact.
    helper = (
        "@njit(cache=False)\ndef cap_tt_key(key, cap_left):\n"
        "    if cap_left > MAX_PLY:\n        return np.uint64(key)\n"
        "    mixed = np.uint64(key) ^ (np.uint64(cap_left + 1) * np.uint64(0xC2B2AE3D27D4EB4F))\n"
        "    return np.uint64(1) if mixed == 0 else mixed\n\n\n")
    source = replace_once(source, "@njit(cache=False)\ndef tt_probe(", helper + "@njit(cache=False)\ndef tt_probe(")
    source = source.replace("tt_probe(st[KEY], ply,", "tt_probe(cap_tt_key(st[KEY], cap_left), ply,")
    source = source.replace("tt_store(st[KEY],", "tt_store(cap_tt_key(st[KEY], cap_left),")
    return source


def fallback_control(source: str) -> str:
    source = add_cap_arguments(source, False)
    source = replace_once(source, "    _adjudicate = adjudicate\n", "    _adjudicate = False\n")
    source = replace_once(source, "    hist_base = list(game_zkeys[:-1] if game_zkeys else [])",
        "    hist_base = list(game_zkeys[:-1] if game_zkeys else [])\n"
        "    cap_left = max(0, 600 - (2 * (int(pos.fullmove) - 1) + int(pos.side)))")
    anchor = "    if ply >= MAX_PLY:\n        return evaluate(pos, adjudicate=_adjudicate)\n"
    terminal = ("    if cap_left <= 0:\n        legal_at_cap = generate_legal(pos)\n"
                "        if not legal_at_cap and in_check(pos, pos.side):\n"
                "            return -MATE + ply\n        return DRAW\n")
    if source.count(anchor) != 2:
        raise ValueError("fallback max-ply anchors")
    source = source.replace(anchor, terminal + anchor)
    helper = ("def _cap_tt_key(key: int, cap_left: int) -> int:\n"
              "    if cap_left > MAX_PLY:\n        return key\n"
              "    mixed = key ^ (((cap_left + 1) * 0xC2B2AE3D27D4EB4F) & ((1 << 64) - 1))\n"
              "    return mixed or 1\n\n\n")
    source = replace_once(source, "def _qsearch(", helper + "def _qsearch(")
    source = source.replace("tt.probe(pos.key)", "tt.probe(_cap_tt_key(pos.key, cap_left))")
    source = source.replace("tt.store(pos.key,", "tt.store(_cap_tt_key(pos.key, cap_left),")
    return source


def main() -> None:
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == EXPECTED
    DEST.mkdir(exist_ok=True)
    originals = {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        for name in archive.namelist():
            assert "/" not in name and name.endswith(".py")
            originals[name] = archive.read(name)
    outputs = dict(originals)
    for name in ("history.py", "eval_nb.py", "time_nb.py", "storm_clock.py", "core_nb.py", "search_nb.py"):
        source = originals[name].decode("utf-8-sig").replace("\r\n", "\n")
        if name == "history.py":
            source = source.replace("PLY_CAP = 300", "PLY_CAP = 600")
            source = replace_once(source, "    return (PLY_CAP - _game_ply) <= ADJUDICATE_WINDOW", "    return False")
            source = replace_once(source,
                "    if _started:\n        _game_ply += 2\n    else:\n        _started = True\n        _game_ply = 0",
                "    _started = True\n    _game_ply = board.ply()")
            source = source.replace("300-ply counter", "absolute 600-ply counter")
        elif name == "eval_nb.py":
            source = replace_once(source, "    if adjudicate:\n        return kingless_material(pos)\n    return pesto(pos)",
                                  "    return pesto(pos)")
        elif name in ("time_nb.py", "storm_clock.py"):
            source = source.replace("PLY_CAP = 300", "PLY_CAP = 600")
        elif name == "core_nb.py":
            source = native_control(source)
        else:
            source = fallback_control(source)
        ast.parse(source)
        outputs[name] = source.encode("utf-8")
    for name, content in outputs.items():
        (DEST / name).write_bytes(content)
    diff = []
    for name in sorted(outputs):
        diff.extend(difflib.unified_diff(
            originals[name].decode("utf-8-sig").replace("\r\n", "\n").splitlines(keepends=True),
            outputs[name].decode("utf-8-sig").replace("\r\n", "\n").splitlines(keepends=True),
            fromfile="original-storm/" + name, tofile=DEST.name + "/" + name))
    (ROOT / "lab/odin/release-control.diff").write_text("".join(diff), encoding="utf-8")
    manifest = {"source_archive": str(ARCHIVE.relative_to(ROOT)), "source_sha256": EXPECTED,
                "control_directory": DEST.name,
                "files": [{"name": name, "sha256": hashlib.sha256(content).hexdigest(),
                           "bytes": len(content), "unchanged_from_storm": content == originals[name]}
                          for name, content in sorted(outputs.items())]}
    (ROOT / "lab/odin/release-control-source.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
