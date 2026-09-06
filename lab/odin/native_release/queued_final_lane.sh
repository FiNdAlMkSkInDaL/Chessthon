#!/bin/bash
set -euo pipefail
stage="$1"
lane="$2"
cpu="$3"
cd "$stage"
while systemctl --user is-active --quiet chesstk-odin-release-validation-r10.service; do sleep 5; done
if [[ "$cpu" == 1 ]]; then
    while systemctl --user is-active --quiet chesstk-odin-queued-material-r8.service; do sleep 5; done
fi
py="$HOME/chess-tk/.venv/bin/python"
"$py" -c 'import hashlib,json,pathlib; p=pathlib.Path("."); assert json.loads((p/"native-gate.json").read_text())["verdict"]=="PASS"; assert json.loads((p/"supplemental.json").read_text())["verdict"]=="PASS"; assert json.loads((p/"state-gate.json").read_text())["status"]=="PASS"; assert hashlib.sha256((p/"candidate-linux-x86.zip").read_bytes()).hexdigest()=="c7d8972e823eb821c016010445d4b02996daff954d870d63083c445850e21102"; assert hashlib.sha256((p/"final112/plan.json").read_bytes()).hexdigest()=="26551be568a8e2fc7eaeb60530fd2c3934c86c8056021c7db840e7414c686734"'
exec "$py" -u lab/odin/native_release/run_final_lane.py --validation-root "$stage" --plan "$stage/final112/plan.json" --candidate "$stage/candidate-linux-x86.zip" --control "$stage/../control-r1/candidate-linux-x86.zip" --original-storm "$stage/../dist/agent-storm-v4-linux-x86.zip" --lane "$lane" --cpu "$cpu"
