"""Original equal-memory two-slot TT after measured destructive collisions."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
audit=json.loads((HERE/'probe-audit.json').read_text());assert audit['audit']=='PASS' and audit['tt_gate_passed']
origin=HERE/'prototypes/control';out=HERE/'prototypes/bucket';out.mkdir(exist_ok=False)
for p in origin.iterdir():
    if p.is_file() and p.suffix in ('.py','.npz'):(out/p.name).write_bytes(p.read_bytes())
s=(origin/'core_nb.py').read_text()
start=s.index('@njit(cache=False)\ndef tt_probe(')
end=s.index('@njit(cache=False)\ndef is_repeat(',start)
s=s[:start]+'''@njit(cache=False)
def tt_probe(key, ply, ttk, ttm, tts, ttd, ttg):
    if key == 0:
        return False, np.int32(0), np.int32(0), np.int32(0), np.int32(0)
    first = np.int64(np.uint64(key) & np.uint64(TT_MASK - 1))
    for idx in range(first, first + 2):
        if ttk[idx] == np.uint64(key):
            return True, ttm[idx], np.int32(ttd[idx]), np.int32(ttg[idx]) & 3, tt_from(np.int32(tts[idx]), ply)
    return False, np.int32(0), np.int32(0), np.int32(0), np.int32(0)


@njit(cache=False)
def tt_store(key, move, depth, flag, score, ply, ttk, ttm, tts, ttd, ttg, tta):
    if key == 0:
        return
    first = np.int64(np.uint64(key) & np.uint64(TT_MASK - 1))
    age = tta[0]
    idx = first
    found = False
    for slot in range(first, first + 2):
        if ttk[slot] == np.uint64(key):
            idx = slot
            found = True
            break
    if not found:
        if ttk[first] == 0:
            idx = first
        elif ttk[first + 1] == 0:
            idx = first + 1
        else:
            # The generation counter cycles through 1..63, skipping zero.
            age0 = (age - (np.int32(ttg[first]) >> 2) + 63) % 63
            age1 = (age - (np.int32(ttg[first + 1]) >> 2) + 63) % 63
            quality0 = np.int32(ttd[first]) + 2 * int((np.int32(ttg[first]) & 3) == EXACT) - 8 * age0
            quality1 = np.int32(ttd[first + 1]) + 2 * int((np.int32(ttg[first + 1]) & 3) == EXACT) - 8 * age1
            idx = first if quality0 <= quality1 else first + 1
    if found and (np.int32(ttg[idx]) >> 2) == age and np.int32(ttd[idx]) > depth:
        return
    if found and move == 0:
        move = ttm[idx]
    packed = max(-32768, min(32767, tt_to(score, ply)))
    ttk[idx] = np.uint64(key)
    ttm[idx] = move
    tts[idx] = np.int16(packed)
    ttd[idx] = np.uint8(min(255, depth))
    ttg[idx] = np.uint8((age << 2) | (flag & 3))


'''+s[end:]
(out/'core_nb.py').write_text(s,newline='\n')
report=dict(source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()},
    gate_evidence_sha256=hashlib.sha256((HERE/'probe-audit.json').read_bytes()).hexdigest(),
    hypothesis='Two-slot buckets protect current deep results with unchanged total entry count. Replacement quality=depth +2 exact -8 per elapsed generation. Parameters are a first design, not tuned strengths.',
    required='Native collision/age/bound/mate/cap/repetition checks; legal diagnostics; equal-wall screen versus narrower control before combination.')
(HERE/'bucket-manifest.json').write_text(json.dumps(report,indent=2));print('Bucket candidate staged')
