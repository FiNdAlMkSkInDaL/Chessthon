"""Create a local source snapshot and exact diff, never a Linux release."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / "odin_history_perf"
BASE = ROOT / "odin"


def sha(data):
    return hashlib.sha256(data).hexdigest()


files = sorted(SOURCE.glob("*.py"))
manifest = {"snapshot_utc": datetime.now(timezone.utc).isoformat(),
            "kind": "Local source snapshot; Linux runtime/release gates pending",
            "source": "odin_history_perf", "base": "odin",
            "source_hashes": {p.name: sha(p.read_bytes()) for p in files},
            "comparison_base_hashes": {p.name: sha((BASE/p.name).read_bytes()) for p in files}}
diff = []
changed = []
for path in files:
    ast.parse(path.read_text(encoding="utf-8"))
    before = (BASE/path.name).read_text(encoding="utf-8").splitlines(keepends=True)
    after = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if before != after:
        changed.append(path.name)
        diff.extend(difflib.unified_diff(before, after, fromfile=f"odin/{path.name}",
                                         tofile=f"odin_history_perf/{path.name}"))
assert changed == ["core_nb.py", "history.py", "search_nb.py"], changed
(HERE / "against-fixed-odin.patch").write_text("".join(diff), encoding="utf-8")
archive = HERE / "odin-history-perf-source.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
    for path in files:
        entry = zipfile.ZipInfo(path.name, (2026, 9, 5, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        output.writestr(entry, path.read_bytes())
manifest.update(archive=archive.name, archive_sha256=sha(archive.read_bytes()),
                changed_files=changed, source_modules=len(files),
                uncompressed_bytes=sum(p.stat().st_size for p in files),
                diff_sha256=sha((HERE/"against-fixed-odin.patch").read_bytes()))
(HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: manifest[k] for k in ("archive", "archive_sha256", "changed_files", "source_modules", "uncompressed_bytes")}, indent=2))
