"""Audit an exact submission ZIP before it reaches the Linux signer.

This deliberately knows only the published packaging contract.  It does not
rebuild source, add stubs, or silently repair the archive being tested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


MAX_UNCOMPRESSED_BYTES = 50_000_000
NATIVE_SUFFIXES = {".a", ".dll", ".dylib", ".exe", ".lib", ".pyd", ".so"}
SHADOWED_ROOT_NAMES = {"chess.py", "types.py"}


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _member_problem(info: zipfile.ZipInfo) -> str | None:
    name = info.filename
    if (
        not name
        or "\\" in name
        or name.startswith("./")
        or "//" in name
    ):
        return f"unsafe ZIP member name: {name!r}"
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return f"unsafe ZIP member path: {name!r}"
    if stat.S_ISLNK(info.external_attr >> 16):
        return f"symlink member is not allowed: {name!r}"
    if info.flag_bits & 0x1:
        return f"encrypted member is not allowed: {name!r}"
    if info.is_dir():
        return None
    lower = path.name.lower()
    if lower.endswith((".pyc", ".pyo")) or "__pycache__" in path.parts:
        return f"compiled Python cache is not allowed: {name!r}"
    if Path(lower).suffix in NATIVE_SUFFIXES:
        return f"native binary is not allowed: {name!r}"
    if len(path.parts) == 1 and path.name in SHADOWED_ROOT_NAMES:
        return f"root module shadows a platform dependency: {name!r}"
    return None


def audit(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise SystemExit(f"not a file: {path}")
    if not zipfile.is_zipfile(path):
        raise SystemExit(f"not a ZIP archive: {path}")

    errors: list[str] = []
    entries: list[dict[str, object]] = []
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [info.filename for info in members]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            errors.append(f"duplicate ZIP members: {', '.join(duplicates)}")
        if names.count("agent.py") != 1:
            errors.append("archive must contain exactly one root agent.py")
        uncompressed = sum(info.file_size for info in members)
        if uncompressed > MAX_UNCOMPRESSED_BYTES:
            errors.append(
                f"uncompressed archive is {uncompressed} bytes; limit is "
                f"{MAX_UNCOMPRESSED_BYTES}"
            )
        for info in members:
            problem = _member_problem(info)
            if problem:
                errors.append(problem)
                continue
            if not info.is_dir():
                entries.append(
                    {
                        "name": info.filename,
                        "compressed_bytes": info.compress_size,
                        "uncompressed_bytes": info.file_size,
                        "sha256": hashlib.sha256(archive.read(info)).hexdigest(),
                    }
                )

    if errors:
        raise SystemExit("release audit failed:\n- " + "\n- ".join(errors))
    return {
        "archive": str(path.resolve()),
        "archive_sha256": _sha256_path(path),
        "zip_bytes": path.stat().st_size,
        "uncompressed_bytes": sum(int(entry["uncompressed_bytes"]) for entry in entries),
        "entries": sorted(entries, key=lambda entry: str(entry["name"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--manifest", type=Path, help="optional JSON output path")
    args = parser.parse_args()
    manifest = audit(args.archive)
    rendered = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
