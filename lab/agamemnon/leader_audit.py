"""Reproducible public four-game timing evidence; no architecture identification."""
import datetime,hashlib,html,io,json,re,statistics,urllib.request,urllib.parse
from pathlib import Path
import chess,chess.pgn,numpy as np
HERE=Path(__file__).resolve().parent
GAMES={39:'be2f66e2-cb20-4800-98d1-ed488461b1d6',38:'6eaedfff-88c6-40ff-9d9e-4872aeda5661',37:'e8fd704b-a562-48cd-8f5e-b8efd9b53973',36:'a4293ded-caef-4bc3-8fa7-9a8c61be2eeb'}
def main():
    rows=[];dest=HERE/'public';total=0
    for rnd,gid in GAMES.items():
        url='https://aichessathon.com/game/'+gid;p=dest/f'leader-r{rnd}.html'
        if not p.exists():p.write_bytes(urllib.request.urlopen(url,timeout=30).read())
        page=p.read_text(encoding='utf8');m=re.search(r'href="data:application/x-chess-pgn;charset=utf-8,([^\"]+)"',page);assert m
        pgn=urllib.parse.unquote(html.unescape(m[1]));(dest/f'leader-r{rnd}.pgn').write_text(pgn,encoding='utf8')
        g=chess.pgn.read_game(io.StringIO(pgn));assert not g.errors;b=g.board();own=g.headers['White']=='Emile Andrieu';clocks={True:120.,False:120.};moves=[]
        for ply,node in enumerate(g.mainline()):
            assert node.move in b.legal_moves;clock=node.clock();assert clock is not None;elapsed=clocks[b.turn]+.5-clock;assert elapsed>=-.002
            if b.turn==own:moves.append(dict(ply=ply,seconds=elapsed,bank=clocks[b.turn],pieces=len(b.piece_map()),uci=node.move.uci()))
            clocks[b.turn]=clock;b.push(node.move);total+=1
        ordinary=[m for m in moves if m['seconds']>.1];x=np.array([[m['bank'],1] for m in ordinary]);y=np.array([m['seconds'] for m in ordinary]);coef=np.linalg.lstsq(x,y,rcond=None)[0];err=y-x@coef
        rows.append(dict(round=rnd,url=url,headers=dict(g.headers),final_bank=clocks[own],own_moves=len(moves),median_seconds={name:statistics.median(m['seconds'] for m in moves if lo<=m['ply']<hi) for name,lo,hi in [('early',0,40),('middle',40,80),('late',80,1000)]},ordinary_fit=dict(n=len(y),slope=float(coef[0]),intercept=float(coef[1]),r2=float(1-np.sum(err**2)/np.sum((y-y.mean())**2)),rmse_seconds=float(np.sqrt(np.mean(err**2)))),timing=moves,html_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pgn_sha256=hashlib.sha256(pgn.encode()).hexdigest()))
    (HERE/'leader-evidence.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),legal_plies=total,games=rows,scope='Filtered descriptive fits: bank and phase covary; no recovered clock algorithm, source, depth, node rate or network identification. Final bank includes increment.'),indent=2));print('legal_plies',total)
if __name__=='__main__':main()
