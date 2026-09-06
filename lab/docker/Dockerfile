# Linux x86_64 signer for our agent — not a two-core match replica, not a train box.
# Contest also has torch and onnxruntime; we omit them so an accidental import fails here.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMBA_NUM_THREADS=1 \
    HOME=/tmp

RUN pip install --no-cache-dir \
    "numpy==2.5.2" \
    "chess==1.11.2" \
    "numba==0.67.0"

WORKDIR /agent
# The signer stages an audited, extracted submission ZIP plus only its probe
# files. Do not enumerate modules here or manufacture missing package files.
COPY . /agent/

# Identity envelope at run time:
#   docker run --cpus=1 --memory=2g --network=none --read-only \
#     --tmpfs /tmp:size=256m --platform linux/amd64 ...
CMD ["python", "release_probe.py"]
