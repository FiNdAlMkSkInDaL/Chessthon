#!/bin/sh
# Pack the already-audited candidate on the Linux x86_64 signer, then smoke
# the exact resulting archive under the strongest unprivileged contest-shaped
# envelope available on the VPS. The caller supplies an isolated staging dir.
set -eu

STAGE=${1:?usage: sign_exact_remote.sh /home/botuser/chess-sign-*}
case "$STAGE" in
    /home/botuser/chess-sign-*) ;;
    *) echo "unsafe signer staging path" >&2; exit 64 ;;
esac

PY=${SIGNER_PYTHON:-/home/botuser/chess-tk/.venv/bin/python}
INCOMING="$STAGE/incoming.zip"
FINAL="$STAGE/agent-v3-linux-x86.zip"
SOURCE="$STAGE/source"
PROBE="$STAGE/probe"
EXPECTED="agent.py board_nb.py core_nb.py eval_nb.py history.py movegen_nb.py search_nb.py tables_nb.py time_nb.py tt_nb.py"

"$PY" - <<'PY'
import chess
import numba
import numpy
import platform
import sys

actual = (
    sys.version_info[:2],
    chess.__version__,
    numpy.__version__,
    numba.__version__,
    platform.machine(),
)
expected = ((3, 12), "1.11.2", "2.5.2", "0.67.0", "x86_64")
if actual != expected:
    raise SystemExit(f"signer identity mismatch: {actual!r}")
print(
    "SIGNER IDENTITY OK python=3.12 chess=1.11.2 "
    "numpy=2.5.2 numba=0.67.0 arch=x86_64"
)
PY

"$PY" "$STAGE/release_audit.py" "$INCOMING" \
    --manifest "$STAGE/incoming-manifest.json"
mkdir "$SOURCE"
"$PY" - "$INCOMING" "$SOURCE" <<'PY'
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

archive, destination = map(Path, sys.argv[1:])
with zipfile.ZipFile(archive) as source:
    for info in source.infolist():
        target = destination.joinpath(*PurePosixPath(info.filename).parts)
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as read, target.open("xb") as write:
                shutil.copyfileobj(read, write)
PY

"$PY" - "$STAGE/incoming-manifest.json" <<'PY'
import json
import sys

expected = [
    "agent.py",
    "board_nb.py",
    "core_nb.py",
    "eval_nb.py",
    "history.py",
    "movegen_nb.py",
    "search_nb.py",
    "tables_nb.py",
    "time_nb.py",
    "tt_nb.py",
]
with open(sys.argv[1], encoding="utf-8") as source:
    manifest = json.load(source)
names = [entry["name"] for entry in manifest["entries"]]
if names != expected:
    raise SystemExit(f"unexpected tested-source members: {names!r}")
print("TESTED SOURCE MEMBERS OK")
PY

"$PY" - "$SOURCE" "$FINAL" <<'PY'
import sys
import zipfile
from pathlib import Path

source, final = map(Path, sys.argv[1:])
names = [
    "agent.py",
    "board_nb.py",
    "core_nb.py",
    "eval_nb.py",
    "history.py",
    "movegen_nb.py",
    "search_nb.py",
    "tables_nb.py",
    "time_nb.py",
    "tt_nb.py",
]
with zipfile.ZipFile(
    final, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
) as archive:
    for name in names:
        archive.write(source / name, arcname=name)
PY
"$PY" "$STAGE/release_audit.py" "$FINAL" \
    --manifest "$STAGE/final-manifest.json"
"$PY" - \
    "$STAGE/incoming-manifest.json" \
    "$STAGE/final-manifest.json" \
    "$FINAL" <<'PY'
import json
import stat
import sys
import zipfile

with open(sys.argv[1], encoding="utf-8") as source:
    incoming = json.load(source)
with open(sys.argv[2], encoding="utf-8") as source:
    final = json.load(source)


def identity(manifest):
    return [
        (entry["name"], entry["uncompressed_bytes"], entry["sha256"])
        for entry in manifest["entries"]
    ]


if identity(incoming) != identity(final):
    raise SystemExit("Linux repack changed tested source bytes")
with zipfile.ZipFile(sys.argv[3]) as archive:
    infos = archive.infolist()
    if any(info.create_system != 3 for info in infos):
        raise SystemExit("final ZIP lacks Unix creator metadata")
    if any(not stat.S_ISREG(info.external_attr >> 16) for info in infos):
        raise SystemExit("final ZIP contains a non-regular member")
print("LINUX REPACK IDENTITY OK creator=Unix source_bytes=exact")
PY

# Re-extract the final archive. The process below tests these exact packaged
# bytes, not the pre-pack source directory.
mkdir "$PROBE"
"$PY" - "$FINAL" "$PROBE" <<'PY'
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

archive, destination = map(Path, sys.argv[1:])
with zipfile.ZipFile(archive) as source:
    for info in source.infolist():
        target = destination.joinpath(*PurePosixPath(info.filename).parts)
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as read, target.open("xb") as write:
                shutil.copyfileobj(read, write)
PY

cp "$STAGE/release_probe.py" "$STAGE/runner.py" "$PROBE/"
mkdir "$PROBE/lab"
cp \
    "$STAGE/lab/__init__.py" \
    "$STAGE/lab/test_hot_path.py" \
    "$STAGE/lab/test_iteration_start.py" \
    "$STAGE/lab/perft.py" \
    "$PROBE/lab/"
find "$PROBE" -type f -exec chmod 0444 {} +
find "$PROBE" -type d -exec chmod 0555 {} +

# This VPS has no Docker-family runtime. Its user systemd manager still gives
# us hard cgroup limits, seccomp address-family isolation, and CPU pinning.
# Submission files are chmod-read-only above; the engine does not write caches.
UNIT="chess-release-v3-$$"
systemd-run --user --quiet --wait --pipe --collect --unit="$UNIT" \
    -p MemoryMax=2147483648 \
    -p MemorySwapMax=0 \
    -p CPUQuota=100% \
    -p TasksMax=128 \
    -p LimitNPROC=128 \
    -p LimitFSIZE=268435456 \
    -p RuntimeMaxSec=180 \
    -p RestrictAddressFamilies=AF_UNIX \
    -p NoNewPrivileges=yes \
    -p UMask=0077 \
    /usr/bin/taskset -c 0 /usr/bin/env \
        PYTHONDONTWRITEBYTECODE=1 \
        HOME=/tmp \
        OMP_NUM_THREADS=1 \
        MKL_NUM_THREADS=1 \
        NUMBA_NUM_THREADS=1 \
        RELEASE_PROBE_ROOT="$PROBE" \
        COLD_IMPORT_TARGET_S=55 \
        COLD_IMPORT_LIMIT_S=60 \
        MOVE_PROBE_LIMIT_S=0.55 \
        HOT_PATH_WALL_LIMIT_S=70 \
        "$PY" "$PROBE/release_probe.py"

echo "EXACT FINAL LINUX-X86 RELEASE GATE OK"
