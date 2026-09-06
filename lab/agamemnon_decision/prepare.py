"""CC0 game-identified roots, frozen before teacher/search collection."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='1'
import io,json,hashlib,sys,urllib.request
from pathlib import Path
import chess,chess.pgn,zstandard
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'lab/agamemnon'))
from public_data_prepare import pesto,phase
sha=lambda b:hashlib.sha256(b).hexdigest()
def key(b):return min(' '.join(b.fen().split()[:4]),' '.join(b.mirror().fen().split()[:4]))
class Filter(chess.pgn.GameBuilder):
    def end_headers(self):
        h=self.game.headers
        try:ok=min(int(h.get('WhiteElo',0)),int(h.get('BlackElo',0)))>=1800 and int(h.get('TimeControl','0').split('+')[0])>=180
        except ValueError:ok=False
        if not ok or h.get('Variant','Standard')!='Standard':return chess.pgn.SKIP
def main():
    dest=HERE/'data';dest.mkdir(exist_ok=True);raw=dest/'standard-2025-01-prefix.zst';url='https://database.lichess.org/standard/lichess_db_standard_rated_2025-01.pgn.zst'
    if not raw.exists():
        request=urllib.request.Request(url,headers={'Range':'bytes=0-67108863','User-Agent':'ChessTK original model research'})
        with urllib.request.urlopen(request,timeout=90) as response:
            assert response.status==206 and response.headers['Content-Range'].startswith('bytes 0-67108863/');data=response.read(67108865);assert len(data)==67108864;raw.write_bytes(data)
            (dest/'download.json').write_text(json.dumps(dict(url=url,range=response.headers['Content-Range'],etag=response.headers.get('ETag'),sha256=sha(data),license='CC0: https://database.lichess.org/',scope='Bounded prefix sample, not representative of all Lichess games.'),indent=2))
    rows=[];families=set();positions=set();gameids=set();visited=0
    with raw.open('rb') as f,zstandard.ZstdDecompressor().stream_reader(f) as reader,io.TextIOWrapper(reader,encoding='utf-8') as stream:
        while len(rows)<3200:
            game=chess.pgn.read_game(stream,Visitor=Filter)
            if game is None:break
            visited+=1;moves=list(game.mainline_moves())
            if game.errors or len(moves)<48:continue
            gameid=game.headers.get('Site','');b=game.board();hist=[];candidates=[];family=None
            if b.fen()!=chess.STARTING_FEN or gameid in gameids:continue
            for ply,m in enumerate(moves[:80],1):
                b.push(m);hist.append(m.uci())
                if ply==20:family=sha(key(b).encode())
                if ply>=24 and ply%2==0 and b.halfmove_clock<60 and not b.is_game_over() and abs(pesto(b,phase(b)))<450:
                    candidates.append((b.fen(),hist.copy(),key(b)))
            if not candidates or family in families:continue
            index=int(sha(gameid.encode())[:8],16)%len(candidates);fen,history,canonical=candidates[index]
            if canonical in positions:continue
            families.add(family);positions.add(canonical);gameids.add(gameid)
            rows.append(dict(id=sha((gameid+fen).encode())[:24],game_id=gameid,family=family,start_fen=chess.STARTING_FEN,history_uci=history,fen=fen,key=canonical,played=moves[len(history)].uci() if len(history)<len(moves) else None))
            if len(rows)%400==0:print('roots',len(rows),'games scanned',visited,flush=True)
    assert len(rows)==3200,(len(rows),visited)
    rows.sort(key=lambda r:sha(('agamemnon-decision-split-v1'+r['family']).encode()))
    for i,r in enumerate(rows):r['split']=0 if i<2560 else (1 if i<2880 else 2)
    # Only nonsealed roots are made available to collectors/training. Group assignments precede labels.
    for name,subset in [('roots.jsonl',rows[:2880]),('sealed-roots.jsonl',rows[2880:])]:
        with (dest/name).open('x') as f:f.write(''.join(json.dumps(r)+'\n' for r in subset))
    plan=dict(roots=3200,train=2560,development=320,sealed=320,games_scanned=visited,game_ids_unique=True,opening20_families_unique=True,root_mirror_keys_unique=True,source_sha256=sha(raw.read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),scope='One root per game and canonical20-ply opening family. Exact/mirror root uniqueness; preserve full UCI history. Later leaf transpositions are audited before fitting. Not proven disjoint from anonymous prior public pretraining. Never read sealed roots during development.')
    (dest/'plan.json').write_text(json.dumps(plan,indent=2));print(json.dumps(plan))

if __name__=='__main__':main()
