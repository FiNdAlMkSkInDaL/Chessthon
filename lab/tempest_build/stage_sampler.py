"""Generate auditable offline-only instrumentation; never edit released search."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
    out=HERE/'sampler-source';out.mkdir(exist_ok=False)
    for p in (ROOT/'tempest').glob('*.py'):(out/p.name).write_bytes(p.read_bytes())
    p=out/'core_nb.py';s=p.read_text()
    # nodes[0:2] retains the exact stop/deadline contract. Everything after it
    # is offline-only sampler storage, passed through existing native calls.
    helper='''
SAMPLE_SLOTS = 40
SAMPLE_WIDTH = 3 + 12 + MAX_PLY
SAMPLE_BASE = 4 + MAX_PLY
SAMPLE_SIZE = SAMPLE_BASE + SAMPLE_SLOTS * SAMPLE_WIDTH

@njit(cache=False)
def sampled_evaluate_nb(bb, st, adjudicate, nodes, ply, kind):
    value = evaluate_nb(bb, st, adjudicate)
    if len(nodes) <= 2 or ply >= MAX_PLY:
        return value
    # Null-search states are not legal trajectories and never enter training.
    for i in range(ply):
        if nodes[4+i] == 0:
            return value
    counter = 2 + kind
    nodes[counter] += 1
    seen = nodes[counter]
    capacity = 32 if kind == 0 else 8
    offset = 0 if kind == 0 else 32
    z = np.uint64(seen) + np.uint64(0x9e3779b97f4a7c15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
    z = z ^ (z >> np.uint64(31))
    slot = seen-1 if seen <= capacity else np.int64(z % np.uint64(seen))
    if slot < capacity:
        base = SAMPLE_BASE + (offset+slot)*SAMPLE_WIDTH
        nodes[base] = ply
        nodes[base+1] = value
        nodes[base+2] = nodes[0]
        for i in range(12):nodes[base+3+i] = np.int64(bb[i])
        for i in range(ply):nodes[base+15+i] = nodes[4+i]
    return value

'''
    index=s.index('@njit(cache=False)\ndef qsearch_nb')
    s=s[:index]+helper+s[index:]
    begin=s.index('def qsearch_nb');end=s.index('\ndef pack_pos',begin)
    search=s[begin:end]
    assert search.count('stand = evaluate_nb(bb, st, adjudicate)')==1
    search=search.replace('stand = evaluate_nb(bb, st, adjudicate)','stand = sampled_evaluate_nb(bb, st, adjudicate, nodes, ply, 0)')
    search=search.replace('static_eval = evaluate_nb(bb, st, adjudicate)','static_eval = sampled_evaluate_nb(bb, st, adjudicate, nodes, ply, 1)')
    for call,idx,mv in [('make_nb(bb, mb, st, move, undos[ply])','ply','move'),('make_null(bb, mb, st, undos[ply])','ply','0'),('make_nb(bb, mb, st, move, undos[0])','0','move')]:
        lines=[]
        for line in search.splitlines(True):
            if line.strip()==call:
                indent=line[:len(line)-len(line.lstrip())]
                lines.append(indent+f'if len(nodes) > 2: nodes[4+{idx}] = {mv}\n')
            lines.append(line)
        search=''.join(lines)
    s=s[:begin]+search+s[end:]
    old='nodes = np.zeros(2, dtype=np.int64)'
    begin=s.index('def search_root(');driver=s[begin:]
    assert driver.count(old)>=1
    driver=driver.replace(old,'nodes = np.zeros(SAMPLE_SIZE, dtype=np.int64)',1)
    driver=driver.replace('    _LAST_NODES = int(nodes[0])','    globals()["_LAB_SAMPLES"] = nodes.copy()\n    _LAST_NODES = int(nodes[0])',1)
    s=s[:begin]+driver;p.write_text(s,encoding='utf-8',newline='\n')
    manifest=dict(source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.py')},baseline={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'tempest').glob('*.py')},scope='Offline search sampler; static observations, not root value labels or PVS exact scores. Reservoir uniform hash approximation over calls, then per-root cap.')
    (HERE/'sampler-manifest.json').write_text(json.dumps(manifest,indent=2));print('sampler staged')
if __name__=='__main__':main()
