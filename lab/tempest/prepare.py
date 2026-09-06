import json,hashlib,re,io,datetime,shutil
from pathlib import Path
import chess,chess.pgn
H=Path(__file__).resolve().parent; R=H.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=json.loads((H/'public/games.json').read_text())
    cases=[]; seen=set(); game_inventory=[]
    old=json.loads((R/'lab/odin/day3/selected-roots.json').read_text())
    for c in old:c.update(split='discovery',group='own-day3-r'+str(c['round']),source_kind='own-known');cases.append(c);seen.add(' '.join(c['fen'].split()[:4]))
    for i,m in enumerate(manifest):
        if 'pgn' not in m:continue
        p=H/m['pgn'];g=chess.pgn.read_game(io.StringIO(p.read_text()));moves=list(g.mainline());b=g.board()
        page=(H/'public'/(m['game_id']+'.html')).read_text(encoding='utf-8')
        op=re.search(r'<dt>Opening</dt><dd>(.*?)</dd>',page);family=op.group(1) if op else ' '.join(b.fen().split()[:4])
        # Hold out whole opening family; never evaluated by default probes.
        split='confirmation' if int(hashlib.sha256(('tempest-family-v1:'+family).encode()).hexdigest()[:8],16)%4==0 else 'discovery'
        game_inventory.append(dict(game_id=m['game_id'],family=family,split=split,headers=dict(g.headers),plies=len(moves),clocks=m['clock_comments']))
        prior=[];clocks={True:120000,False:120000}
        for ply,n in enumerate(moves):
            if ply in (12,32,64) and b.outcome(claim_draw=True) is None:
                key=' '.join(b.fen().split()[:4])
                if key not in seen:
                    cases.append(dict(id=m['game_id']+'-p'+str(ply),fen=b.fen(),start_fen=g.board().fen(),history_uci=prior.copy(),storm_colour='white' if b.turn else 'black',time_left_ms=round(clocks[b.turn]),played_uci=n.move.uci(),played_san=b.san(n.move),split=split,group=family,game_id=m['game_id'],source_kind='public',team=m['team'],round=g.headers['Round'],ply=ply));seen.add(key)
            if n.clock() is not None:clocks[b.turn]=n.clock()*1000
            prior.append(n.move.uci());b.push(n.move)
    # Original construction, not a tactical answer collection. No claim of unbiased game distribution.
    for i,fen in enumerate(['8/8/3k4/3p4/3P4/3K4/8/8 w - - 0 40','6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 30','r3k2r/ppp2ppp/2n5/3pp3/3PP3/2N5/PPP2PPP/R3K2R w KQkq - 0 10','6k1/8/2P5/3P4/8/1p6/8/6K1 w - - 0 40']):
        b=chess.Board(fen);assert b.is_valid()
        cases.append(dict(id='constructed-'+str(i),fen=fen,start_fen=fen,history_uci=[],storm_colour='white',time_left_ms=120000,split='discovery',group='constructed-'+str(i),source_kind='constructed',ply=0,round=0))
    (H/'corpus-v1.json').write_text(json.dumps(cases,indent=2))
    (H/'split-manifest.json').write_text(json.dumps(game_inventory,indent=2))
    focus=[c['id'] for c in cases if c['source_kind']!='public']
    for team in dict.fromkeys(m['team'] for m in manifest):
        focus += [c['id'] for c in cases if c.get('team')==team and c['split']=='discovery'][:2]
    plan=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),baseline={p.name:sha(p) for p in sorted((R/'odin_v6').glob('*.py'))},corpus_sha256=sha(H/'corpus-v1.json'),focus=focus,variants=['baseline','lmr_off','futility_off','see_off','null_off','pesto_only'],budgets=[200000,1000000],wall_ms=1500,criteria='Diagnostic only: paired same-root finite-reference regret, wins/losses beyond 30cp. Reject blanket changes with material average/tail regression or wall cost. No release decision from this corpus. Confirmation families remain unsearched. All variants reported.',instrumentation='Direct native search_root with reconstructed served history; clean native module arrays per root. Fixed-node driver substitutions as prior worker. Full root trace retained. No production mutation. ARM timing descriptive only.')
    (H/'experiment-plan.json').write_text(json.dumps(plan,indent=2))
    print(len(cases),len(focus),len([c for c in cases if c['split']=='confirmation']))
if __name__=='__main__':main()
