"""Create the isolated sparse-NMP experiment from the frozen history r2 ZIP."""
from __future__ import annotations
import ast
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "lab/odin/history_perf/odin-history-perf-source.zip"
EXPECTED = "d9f4a18f1fa262fcb6170c281f3e7e937f73485409f4205020bf2cbd27b084a3"
DEST = ROOT / "odin_sparse_guard"
HERE = Path(__file__).resolve().parent


def main():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == EXPECTED
    with zipfile.ZipFile(BASE) as archive:
        originals = {name: archive.read(name) for name in archive.namelist()}
    assert len(originals) == 12 and all("/" not in name and name.endswith(".py") for name in originals)
    outputs = dict(originals)
    source = originals["core_nb.py"].decode("utf-8").replace("\r\n", "\n")
    anchor = "            and has_nm_pieces(bb, np.int32(st[SIDE]))\n        ):\n            vulnerable_null = not nmp_safe_nb(bb)\n"
    assert source.count(anchor) == 1
    source = source.replace(anchor,
        "            and has_nm_pieces(bb, np.int32(st[SIDE]))\n"
        "            and nmp_safe_nb(bb)\n        ):\n")
    start = source.index("            if score >= beta:\n                if vulnerable_null:\n")
    end = source.index("\n    if hash_move == 0 and depth >= IIR_MIN_D", start)
    source = source[:start] + (
        "            if score >= beta:\n"
        "                if score >= MATE_WIN:\n"
        "                    return beta\n"
        "                return score\n") + source[end:]
    assert "vulnerable_null" not in source and "verify = negamax_nb" not in source
    ast.parse(source)
    outputs["core_nb.py"] = source.encode("utf-8")
    DEST.mkdir(exist_ok=True)
    for name, data in outputs.items():
        (DEST / name).write_bytes(data)
    diff = "".join(difflib.unified_diff(
        originals["core_nb.py"].decode("utf-8").replace("\r\n", "\n").splitlines(True),
        source.splitlines(True), fromfile="history-perf-r2/core_nb.py", tofile="sparse-guard/core_nb.py"))
    (HERE / "against-history-r2.patch").write_text(diff, encoding="utf-8")
    snapshot = HERE / "odin-sparse-guard-source.zip"
    with zipfile.ZipFile(snapshot, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(outputs.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 5, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    manifest = {"base_zip_sha256": EXPECTED, "source_only_not_release": True,
                "source_zip": str(snapshot.relative_to(ROOT)),
                "source_zip_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                "files": [{"name": name, "sha256": hashlib.sha256(data).hexdigest(),
                           "bytes": len(data), "unchanged_from_r2": data == originals[name]}
                          for name, data in sorted(outputs.items())]}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
