#!/bin/sh
# Example only. Run on the Linux x86_64 signer after collectors are paused.
# Supply the ZIP that will be tested; the gate extracts that exact archive and
# never fills in missing modules from the repository tree.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
ARCHIVE=${1:?usage: run-signer.example.sh candidate.zip}
exec "$ROOT/lab/docker/freeze_audit.sh" "$ARCHIVE"
