"""Fuse original24-feature evaluation into direct weighted accumulators."""
import argparse,json,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ROOT/'odin_submission');ap.add_argument('--output',type=Path,default=ROOT/'odin_fused');args=ap.parse_args()
out=args.output.resolve();out.mkdir(exist_ok=False)
for p in args.source.glob('*.py'):shutil.copy2(p,out/p.name)
p=out/'core_nb.py';s=p.read_text(encoding='utf-8')
weights={phase:json.loads(re.search(r'FEATURE_'+phase+r' = np.array\((\[[^\n]+?\]), dtype=np.int32\)',s).group(1)) for phase in ('MG','EG')}
start=s.index('def positional_features_nb(');end=s.index('\n\n\n@njit',start);body=s[start:end]
original_start=s.index('def positional_correction_nb(');original_end=s.index('\n\n\n@njit',original_start)
tail=s[s.index('    phase = ',original_start):original_end]
body=body.replace('def positional_features_nb(bb, st):','def positional_correction_nb(bb, st):').replace('    features = np.zeros(24, dtype=np.int32)','    mg = 0\n    eg = 0')
lines=[]
for line in body.splitlines():
    m=re.match(r'(\s*)features\[(.*?)\] \+= (.*)',line)
    if m:
        indent,idx,expr=m.groups()
        for phase in ('MG','EG'):
            coef=str(weights[phase][int(idx)]) if idx.isdigit() else f'FEATURE_{phase}[{idx}]'
            if coef!='0':lines.append(f'{indent}{phase.lower()} += ({expr}) * ({coef})')
    elif line.strip()=='return features':
        lines += tail.splitlines()
    else:lines.append(line)
new='\n'.join(lines)
a=s.index('def positional_correction_nb(');b=s.index('\n\n\n@njit',a)
s=s[:a]+new+s[b:];p.write_text(s,encoding='utf-8',newline='\n')
print('Created arithmetic-equivalent fused evaluator; must pass feature equivalence and throughput tests before use.')
