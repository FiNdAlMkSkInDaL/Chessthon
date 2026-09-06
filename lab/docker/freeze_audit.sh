#!/bin/sh
# Exact-ZIP release gate on the Linux signer under the contest envelope.
# Run from repo root after collectors pause. This never rebuilds or repairs a ZIP.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
ARCHIVE=${1:?usage: freeze_audit.sh /absolute/or/relative/candidate.zip}
PYTHON=${PYTHON:-python3}
if [ ! -f "$ARCHIVE" ]; then
  echo "missing ZIP: $ARCHIVE" >&2
  exit 1
fi
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
"$PYTHON" "$ROOT/lab/release_audit.py" "$ARCHIVE" --manifest "$STAGE/manifest.json"
"$PYTHON" - "$ARCHIVE" "$STAGE" <<'PY'
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
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open(info) as read, target.open("xb") as write:
            shutil.copyfileobj(read, write)
PY
cp "$ROOT/lab/docker/release_probe.py" "$STAGE/release_probe.py"
mkdir -p "$STAGE/lab"
cp "$ROOT/lab/test_hot_path.py" "$ROOT/lab/test_iteration_start.py" "$ROOT/lab/perft.py" "$STAGE/lab/"
cp "$ROOT/harness/runner.py" "$STAGE/runner.py"
docker build --platform linux/amd64 -f "$ROOT/lab/docker/Dockerfile" -t chess-tk-freeze "$STAGE"
docker run --rm \
  --platform linux/amd64 \
  --cpus=1 \
  --memory=2g \
  --memory-swap=2g \
  --network=none \
  --read-only \
  --pids-limit=128 \
  --tmpfs /tmp:size=256m \
  --env COLD_IMPORT_TARGET_S=55 \
  --env COLD_IMPORT_LIMIT_S=60 \
  chess-tk-freeze
echo "EXACT-ZIP LINUX SIGNER GATE OK"
