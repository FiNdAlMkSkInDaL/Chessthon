"""Allowlisted offline screening transport, never a submission archive."""
from pathlib import Path
import zipfile,hashlib,json
root=Path(__file__).resolve().parents[3]
out=root/'lab/odin/fast/transport.zip'
files=[]
for d in ('odin_submission','odin_v6_aspiration','odin_v6_selective','lab/odin/fast'):
    files.extend((root/d).glob('*.py'))
for f in ('lab/odin/fast/screen-openings/openings.fen','lab/odin/fast/screen-policy.json','lab/odin/fast/candidates.json'):
    files.append(root/f)
with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(files):z.write(f,f.relative_to(root).as_posix())
print(json.dumps({'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'members':len(files)}))
