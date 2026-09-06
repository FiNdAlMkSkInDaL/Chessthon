"""Allowlisted generation screening transport; not uploadable engine archive."""
import json,zipfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
files=list((ROOT/'odin_generation').glob('*/*.py'))+list((ROOT/'odin_submission').glob('*.py'))
files += [HERE/n for n in ('worker.py','match.py','population.py','generation-policy.json','generation-openings/screen.fen','generation-openings/confirm.fen')]
with zipfile.ZipFile(HERE/'generation-transport.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(ROOT).as_posix())
print(json.dumps({'members':len(files),'sha256':hashlib.sha256((HERE/'generation-transport.zip').read_bytes()).hexdigest()}))
