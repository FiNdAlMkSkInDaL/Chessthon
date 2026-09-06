import subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent
for v in ('baseline','lmr_off','futility_off','see_off','null_off','pesto_only'):
    with (H/(v+'.stdout')).open('x') as out,(H/(v+'.stderr')).open('x') as err:
        cmd=[sys.executable,'-B',str(H/'probe.py'),'--variant',v,'--cpu','4']+(['--wide'] if v=='baseline' else [])
        p=subprocess.run(cmd,stdout=out,stderr=err)
        if p.returncode:raise RuntimeError((v,p.returncode))
