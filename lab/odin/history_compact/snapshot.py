"""Freeze compact experiment source and exact diff against history-perf r2."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / "odin_history_compact"
BASE = ROOT / "odin_history_perf"
files = sorted(SOURCE.glob("*.py"))
hashes = lambda directory: {p.name: hashlib.sha256((directory/p.name).read_bytes()).hexdigest() for p in files}
diff = []
changed = []
for path in files:
    ast.parse(path.read_text(encoding="utf-8"))
    before = (BASE/path.name).read_text(encoding="utf-8").splitlines(keepends=True)
    after = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if before != after:
        changed.append(path.name)
        diff.extend(difflib.unified_diff(before, after, fromfile=f"odin_history_perf/{path.name}", tofile=f"odin_history_compact/{path.name}"))
assert changed == ["core_nb.py"]
(HERE/"against-history-perf-r2.patch").write_text("".join(diff), encoding="utf-8")
archive = HERE/"odin-history-compact-source.zip"
with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as out:
    for path in files:
        entry=zipfile.ZipInfo(path.name,(2026,9,5,0,0,0))
        entry.compress_type=zipfile.ZIP_DEFLATED
        entry.external_attr=0o100644<<16
        out.writestr(entry,path.read_bytes())
manifest={"snapshot_utc":datetime.now(timezone.utc).isoformat(),
          "kind":"Local experimental source snapshot; native gates and strength unmeasured",
          "source":"odin_history_compact", "base":"odin_history_perf", "source_sha256":hashes(SOURCE),
          "base_sha256":hashes(BASE), "changed_files":changed, "archive":archive.name,
          "archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
          "source_modules":len(files),"uncompressed_bytes":sum(p.stat().st_size for p in files)}
(HERE/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:manifest[k] for k in ("archive","archive_sha256","changed_files","uncompressed_bytes")},indent=2))
