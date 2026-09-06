#!/bin/sh
# Pack an immutable Storm snapshot on Linux, then exercise the final bytes.
set -eu
STAGE=${1:?absolute staging directory required}
case "$STAGE" in "$HOME"/chess-sign-storm-*) ;; *) exit 64 ;; esac
PY=${SIGNER_PYTHON:-"$HOME/chess-tk/.venv/bin/python"}
cd "$STAGE"
"$PY" - "$STAGE" <<'PY'
import json, platform, sys, zipfile
from pathlib import Path
import chess, numba, numpy
from lab.release_audit import audit
stage=Path(sys.argv[1]).resolve()
assert platform.machine()=='x86_64' and sys.version_info[:2]==(3,12)
assert (chess.__version__,numpy.__version__,numba.__version__)==('1.11.2','2.5.2','0.67.0')
incoming=audit(stage/'incoming.zip')
names=[e['name'] for e in incoming['entries']]
assert all('/' not in n and n.endswith('.py') for n in names)
source=stage/'source'; source.mkdir()
with zipfile.ZipFile(stage/'incoming.zip') as z:
    z.extractall(source)
final=stage/'storm-v4-linux-x86.zip'
with zipfile.ZipFile(final,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name in names: z.write(source/name,name)
manifest=audit(final)
assert [(e['name'],e['sha256']) for e in incoming['entries']]==[(e['name'],e['sha256']) for e in manifest['entries']]
with zipfile.ZipFile(final) as z:
    assert all(i.create_system==3 for i in z.infolist())
    probe=stage/'probe'; probe.mkdir(); z.extractall(probe)
for path in probe.iterdir(): path.chmod(0o444)
probe.chmod(0o555)
(stage/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('LINUX SOURCE IDENTITY PASS',manifest['archive_sha256'],flush=True)
PY
systemd-run --user --quiet --wait --pipe --collect --unit="storm-gate-$$" \
    -p MemoryMax=2147483648 -p MemorySwapMax=0 -p CPUQuota=100% \
    -p TasksMax=128 -p RuntimeMaxSec=240 -p RestrictAddressFamilies=AF_UNIX \
    -p NoNewPrivileges=yes -p LimitFSIZE=268435456 \
    /usr/bin/taskset -c 0 /usr/bin/env \
    PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 \
    PYTHONPATH="$STAGE" STORM_SOURCE="$STAGE/probe" \
    "$PY" -m lab.storm.gates
systemd-run --user --quiet --wait --pipe --collect --unit="storm-cold-$$" \
    -p MemoryMax=2147483648 -p MemorySwapMax=0 -p CPUQuota=100% \
    -p TasksMax=128 -p RuntimeMaxSec=110 -p RestrictAddressFamilies=AF_UNIX \
    -p NoNewPrivileges=yes /usr/bin/taskset -c 0 /usr/bin/env \
    PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONPATH="$STAGE" \
    "$PY" -m lab.storm.protocol_probe "$STAGE/probe"
echo 'STORM EXACT LINUX RELEASE GATES PASS'
