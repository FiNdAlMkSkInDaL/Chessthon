# Runtime image for one exact submission ZIP in a competition-shaped match.
# The build context is created by lab.container_match from an audited ZIP and
# contains only agent/ plus byte-for-byte copies of harness/runner.py and the
# lab-owned pre-match probe (outside the submitted agent directory).
#
# This reproduces the engine-relevant pinned dependencies and resource
# envelope. The private full platform image and tournament CPU are unknown.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMBA_NUM_THREADS=1 \
    HOME=/tmp \
    NUMBA_CACHE_DIR=/tmp/numba-cache

# Deliberately omit torch/onnxruntime: neither submitted engine uses them, and
# an accidental dependency should fail this gate rather than consume RAM.
RUN pip install --no-cache-dir \
    "numpy==2.5.2" \
    "chess==1.11.2" \
    "numba==0.67.0"

COPY agent/ /agent/
COPY runner.py /harness/runner.py
COPY image_probe.py /harness/image_probe.py
WORKDIR /agent

CMD ["python", "/harness/runner.py", "/agent"]
