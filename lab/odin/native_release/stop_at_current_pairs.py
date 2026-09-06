"""User-directed early stop, preserving completed pairs and all original evidence."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

stage=Path(__file__).resolve().parents[3]
pending={'a','b'}
end=time.monotonic()+1800
print(json.dumps({'event':'USER_DIRECTED_SAMPLE_CHANGE','target_games_per_lane':8,
                  'reason':'User rejects waiting for112 games and prioritizes rapid iteration. No claim that the original confidence gate passed.'}),flush=True)
while pending and time.monotonic()<end:
    for lane in list(pending):
        path=stage/f'final112/primary-{lane}.jsonl'
        rows=[json.loads(s) for s in path.read_text().splitlines() if s.strip()]
        count=sum(r.get('type')=='game' for r in rows)
        if count<8:continue
        unit=f'chesstk-odin-final-r10-{lane}.service'
        query=subprocess.run(['systemctl','--user','show',unit,'--property=MainPID','--value'],capture_output=True,text=True,check=True)
        parent=int(query.stdout.strip())
        assert parent>0
        parent_args=Path(f'/proc/{parent}/cmdline').read_bytes().split(b'\0')
        assert any(b'run_final_lane.py' in a for a in parent_args) and str(stage).encode() in parent_args
        found=[]
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():continue
            try:
                status=dict(line.split(':',1) for line in (proc/'status').read_text().splitlines() if ':' in line)
                if int(status['PPid'])!=parent:continue
                argv=(proc/'cmdline').read_bytes().split(b'\0')
                if b'lab.odin.release.linux_match' in argv and str(path).encode() in argv:
                    found.append(int(proc.name))
            except (FileNotFoundError,ProcessLookupError,PermissionError):continue
        assert len(found)==1,found
        os.kill(found[0],signal.SIGINT)
        print(json.dumps({'event':'PAIR_BOUNDARY_STOP_REQUESTED','lane':lane,'complete_games':count,'match_pid':found[0]}),flush=True)
        pending.remove(lane)
    if pending:time.sleep(.25)
assert not pending
