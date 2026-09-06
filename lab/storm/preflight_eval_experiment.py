"""Pack and cold-import the isolated r3 experiment; never an upload artifact."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lab.laptop_match import MEMORY_LIMIT_BYTES, runner_command
from lab.laptop_runner import DIAGNOSTIC_PREFIX
from lab.release_audit import audit


def main():
    source = ROOT / "dist/storm-eval-r3"
    archive = ROOT / "dist/storm-eval-r3-experimental-windows.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as packed:
        for path in sorted(source.glob("*.py")):
            packed.write(path, path.name)
    manifest = audit(archive)
    report = {"archive": str(archive), "archive_manifest": manifest,
              "status": "experimental Windows comparison only; not approved for upload"}
    with tempfile.TemporaryDirectory(prefix="storm-eval-r3-preflight-") as temporary:
        temp = Path(temporary).resolve()
        assert temp.parent == Path(tempfile.gettempdir()).resolve()
        assert temp.name.startswith("storm-eval-r3-preflight-")
        payload = temp / "payload"
        payload.mkdir()
        with zipfile.ZipFile(archive) as packed:
            packed.extractall(payload)  # members already checked by release_audit
        command = runner_command(payload, temp / "runner-home", 8, MEMORY_LIMIT_BYTES)
        started = time.perf_counter()
        result = subprocess.run(command, input="", capture_output=True, text=True, timeout=90)
        elapsed = time.perf_counter() - started
        diagnostics = [json.loads(line[len(DIAGNOSTIC_PREFIX):])
                       for line in result.stderr.splitlines() if line.startswith(DIAGNOSTIC_PREFIX)]
        report.update({"elapsed_s": elapsed, "exit_code": result.returncode,
                       "stdout": result.stdout, "stderr": result.stderr,
                       "runner_diagnostics": diagnostics})
        output = ROOT / "lab/storm/eval_r3_cold_preflight.json"
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        assert result.returncode == 0, report
        assert any(json.loads(line).get("ready") for line in result.stdout.splitlines()), report
        assert diagnostics, report
        evidence = diagnostics[-1]
        assert evidence["import_s"] < 90 and elapsed < 90, evidence
        assert evidence["numba"]["compiled"] is True, evidence
        assert evidence["numba"]["effective_ready"] is True, evidence
        assert evidence["numba"]["original_ready"] is True, evidence
        report["passed"] = True
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"passed": True, "import_s": evidence["import_s"],
                          "elapsed_s": elapsed, "archive_sha256": manifest["archive_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
