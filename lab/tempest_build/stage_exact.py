"""Isolate an exact-endgame candidate; preserve the rules-only fallback."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
    dst=ROOT/'tempest_exact';dst.mkdir(exist_ok=False)
    for p in (ROOT/'tempest').glob('*.py'):(dst/p.name).write_bytes(p.read_bytes())
    for p in [HERE/'endgame_exact.py',HERE/'three-piece/three_piece_dtm.npz']:(dst/p.name).write_bytes(p.read_bytes())
    p=dst/'agent.py';s=p.read_text();s=s.replace('import history\n','import history\nfrom endgame_exact import choose_exact\n',1)
    old='    history.observe_served(board)\n'
    assert s.count(old)==1
    s=s.replace(old,old+'''    exact = choose_exact(board, history._seen)
    if exact is not None:
        history.observe_our_uci(board, exact)
        return exact
''',1)
    s=s.replace('# Odin v6. Direct legality', '# Tempest exact-endgame candidate, derived from Odin v6. Direct legality')
    p.write_text(s,encoding='utf-8',newline='\n')
    (HERE/'exact-manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dst.iterdir()},indent=2));print('exact candidate staged')
if __name__=='__main__':main()
