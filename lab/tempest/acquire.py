"""Public HTTP pages and PGNs from observed HTML links, no private endpoints."""
import urllib.request, urllib.parse, re, json, hashlib, datetime, html, io
from pathlib import Path
import chess.pgn
HERE=Path(__file__).resolve().parent
OUT=HERE/'public'; OUT.mkdir(exist_ok=True)
def digest(b): return hashlib.sha256(b).hexdigest()
def fetch(url,name):
    p=OUT/name
    if p.exists(): return p.read_text(encoding='utf-8')
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        with urllib.request.urlopen(url,timeout=40) as r:
            data=r.read(); status=r.status; headers=dict(r.headers)
        p.write_bytes(data)
        row=dict(url=url,path=str(p.relative_to(HERE)),utc=now,status=status,sha256=digest(data),headers=headers)
    except Exception as e:
        row=dict(url=url,utc=now,error=str(e)); data=b''
    with (OUT/'fetches.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
    return data.decode('utf-8',errors='replace')
def plain(s):return html.unescape(re.sub('<[^>]+>',' ',s))
TEAMS={'ms':'c3e1bc09-3d21-4279-ace0-16bb3742f5da','AI Fellows':'b574c0ea-e994-4a16-9918-7fbc989c4234','AlphaFish':'659a3020-8af7-4934-b753-3b7c5fd11184','Capablanca':'c7fad433-1020-4b2a-a0e3-8e86720d23de','FuzzyBot':'3241cef5-6b1c-41f2-b275-f0e50fc52ed5','adashima':'e356ff20-37e4-4fc4-bfef-00cf5957a82c'}
def main():
    for path in ('docs/agent-contract.md','docs/rules.md','docs','rules','leaderboard'):
        fetch('https://aichessathon.com/'+path,path.replace('/','_')+'.html')
    for path in ('harness/referee.py','harness/rules.py','harness/runner.py'):
        fetch('https://raw.githubusercontent.com/advitrocks9/aichessathon-starter/main/'+path,'starter-'+path.split('/')[-1])
    manifest=[]; inventory=[]; seen=set()
    for name,tid in TEAMS.items():
        page=fetch('https://aichessathon.com/team/'+tid+'?from=lb',tid+'.html')
        rows=[]
        for tr in re.findall(r'<tr\b[^>]*>.*?</tr>',page,re.S):
            m=re.search(r'href="(/game/[^"\s]+)"',tr)
            if not m:continue
            text=' '.join(plain(tr).split()); url=html.unescape(m[1]); gid=url.split('/game/')[1].split('?')[0]
            rows.append(dict(team=name,game_id=gid,url='https://aichessathon.com'+url,text=text,void='Void' in text))
        inventory+=rows
        # Fixed manageable stratification: recent nonvoid white+black and one win/draw/loss each, max 5/team.
        selected=[]
        for token in ('White','Black','Win','Draw','Loss'):
            candidate=next((r for r in rows if not r['void'] and token in r['text'] and r not in selected and any(x in r['text'] for x in ('Win','Loss','Draw'))),None)
            if candidate:selected.append(candidate)
        for row in selected:
            gid=row['game_id']
            if gid in seen:continue
            seen.add(gid)
            game=fetch(row['url'],gid+'.html')
            m=re.search(r'href="data:application/x-chess-pgn[^,]*,([^"]+)"',game)
            if not m: row['error']='No public PGN link';manifest.append(row);continue
            pgn=urllib.parse.unquote(html.unescape(m[1])); p=OUT/(gid+'.pgn');p.write_text(pgn,encoding='utf-8')
            g=chess.pgn.read_game(io.StringIO(pgn));b=g.end().board()
            row.update(pgn=str(p.relative_to(HERE)),sha256=digest(p.read_bytes()),headers=dict(g.headers),plies=len(list(g.mainline_moves())),legal=not g.errors,final_fen=b.fen(),referee_outcome=str(b.outcome(claim_draw=True)),clock_comments=sum(n.clock() is not None for n in g.mainline()))
            row['page_status']=' '.join(plain(game[game.find('<main'):game.find('replay-panel')]).split())[:1000]
            manifest.append(row); print(name,gid,row['plies'],flush=True)
    (OUT/'team-inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    (OUT/'games.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
if __name__=='__main__':main()
