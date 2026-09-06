import json,io,collections,statistics,hashlib,re,sys
from pathlib import Path
import chess,chess.pgn
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H));from acquire import fetch,TEAMS,plain
def main():
    manifest=json.loads((H/'public/games.json').read_text());updates={}
    for name,tid in TEAMS.items():
        page=fetch('https://aichessathon.com/team/'+tid+'?from=lb',tid+'-recheck.html')
        for tr in re.findall(r'<tr\b[^>]*>.*?</tr>',page,re.S):
            m=re.search(r'/game/([a-f0-9-]+)',tr)
            if m:updates.setdefault(m[1],[]).append(dict(team=name,text=' '.join(plain(tr).split())))
    rows=[]
    for m in manifest:
        if 'pgn' not in m:continue
        g=chess.pgn.read_game(io.StringIO((H/m['pgn']).read_text()));b=g.board();first=None;clocks={True:120.,False:120.};timing={True:[],False:[]};final={}
        for ply,n in enumerate(g.mainline()):
            outcome=b.outcome(claim_draw=True)
            if first is None and (outcome or b.ply()>=600):first=dict(ply=ply,absolute=b.ply(),outcome=str(outcome))
            if n.clock() is not None:
                elapsed=clocks[b.turn]+.5-n.clock();timing[b.turn].append(dict(ply=ply,seconds=elapsed,legal=b.legal_moves.count(),pieces=len(b.piece_map()),clock_before=clocks[b.turn]));clocks[b.turn]=n.clock()
            b.push(n.move)
        for c in (True,False):
            ts=timing[c];final['white' if c else 'black']=dict(player=g.headers['White' if c else 'Black'],moves=len(ts),final_clock=clocks[c],median_seconds=statistics.median(t['seconds'] for t in ts) if ts else None,negative_elapsed=sum(t['seconds']<-.002 for t in ts),early_median=statistics.median([t['seconds'] for t in ts if t['ply']<40]) if ts else None,late_median=statistics.median([t['seconds'] for t in ts if t['ply']>=80]) if any(t['ply']>=80 for t in ts) else None)
        current=updates.get(m['game_id'],[]);void=any('Void' in x['text'] for x in current) or m['void'];rated=not void and g.headers['Result']!='*' and 'Final' in m['page_status']
        rows.append(dict(game_id=m['game_id'],headers=dict(g.headers),rated_at_retrieval=rated,recheck=current,void=void,first_current_referee_terminal_before_recorded_end=first,timing=final))
    (H/'public-audit.json').write_text(json.dumps(rows,indent=2));print(len(rows),sum(r['rated_at_retrieval'] for r in rows))
if __name__=='__main__':main()
