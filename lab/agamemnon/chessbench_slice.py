"""Bounded original HTTP-range reader for permitted ChessBench TRAINING data.

Format references: DeepMind bagz.py/constants.py, Apache Beam nested UTF8 and
big-endian FloatCoder. No model, engine, or engine implementation is downloaded.
Data attribution: Ruoss et al., Google DeepMind, NeurIPS 2024, CC-BY 4.0; underlying
Lichess portions CC0. Derivative numeric arrays remain OFFLINE training data.
"""
import concurrent.futures,datetime,hashlib,json,math,struct,time,urllib.request
from pathlib import Path
import chess
import numpy as np
HERE=Path(__file__).resolve().parent
URL='https://storage.googleapis.com/searchless_chess/data/train/state_value_data.bag'

def fetch(start,end,etag=None):
    assert 0<=start<=end and end-start<4_000_000
    headers={'Range':f'bytes={start}-{end}'}
    if etag:headers['If-Match']=etag
    with urllib.request.urlopen(urllib.request.Request(URL,headers=headers),timeout=45) as r:
        assert r.status==206 and r.headers['Content-Range'].startswith(f'bytes {start}-{end}/')
        data=r.read(end-start+2);assert len(data)==end-start+1
        if etag:assert r.headers['ETag']==etag
        return data,dict(r.headers)

def decode(record):
    length=0;shift=0;pos=0
    while True:
        b=record[pos];pos+=1;length|=(b&127)<<shift;shift+=7
        if not b&128:break
        assert shift<21
    assert 15<=length<=120 and pos+length+8==len(record)
    fen=record[pos:pos+length].decode('utf8');prob=struct.unpack('>d',record[-8:])[0]
    assert math.isfinite(prob) and 0<=prob<=1
    return fen,prob

def main():
    dest=HERE/'chessbench';dest.mkdir(exist_ok=False);started=time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request(URL,headers={'Range':'bytes=-8'}),timeout=30) as r:
        assert r.status==206;tail=r.read(9);assert len(tail)==8
        size=int(r.headers['Content-Range'].split('/')[-1]);etag=r.headers['ETag'];generation=r.headers.get('x-goog-generation')
    index=struct.unpack('<Q',tail)[0];assert 0<index<size and (size-index)%8==0
    total=(size-index)//8;rng=np.random.default_rng(20260906)
    # Dispersed nonoverlapping blocks, fixed before inspecting any labels.
    starts=[]
    while len(starts)<20:
        n=int(rng.integers(1,total-10000))
        if all(abs(n-other)>20000 for other in starts):starts.append(n)
    plan=dict(url=URL,etag=etag,generation=generation,remote_bytes=size,records=total,index_start=index,block_records=10000,starts=starts,training_blocks=list(range(16)),development_blocks=[16,17],sealed_blocks=[18,19],seed=20260906,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Public training split only. Block partitions have no game IDs; exact-position separation is enforced downstream, no opening-family independence claim. Blocks18/19 are acquired but not decoded or fitted. No models or runtime lookup data acquired.',attribution='ChessBench: Ruoss et al., Google DeepMind, NeurIPS2024; CC-BY4.0, underlying Lichess CC0',source='https://github.com/google-deepmind/searchless_chess')
    (dest/'plan.json').write_text(json.dumps(plan,indent=2))
    def block(i):
        record_start=starts[i];limits,headers=fetch(index+8*(record_start-1),index+8*(record_start+10000)-1,etag)
        offsets=np.frombuffer(limits,dtype='<u8');assert len(offsets)==10001 and np.all(offsets[1:]>offsets[:-1])
        begin,end=int(offsets[0]),int(offsets[-1]);assert end<=index
        data,_=fetch(begin,end-1,etag)
        (dest/f'block-{i:02d}.bin').write_bytes(data);(dest/f'offsets-{i:02d}.bin').write_bytes(limits)
        return dict(block=i,first_record=record_start,record_count=10000,byte_start=begin,bytes=len(data),limits_sha256=hashlib.sha256(limits).hexdigest(),sha256=hashlib.sha256(data).hexdigest())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        blocks=list(pool.map(block,range(20)))
    for entry in blocks:
        i=entry['block']
        if i>=18:continue
        data=(dest/f'block-{i:02d}.bin').read_bytes();offsets=np.frombuffer((dest/f'offsets-{i:02d}.bin').read_bytes(),dtype='<u8');origin=int(offsets[0]);valid=0
        with (dest/f'rows-{i:02d}.jsonl').open('x') as f:
            for j in range(10000):
                fen,p=decode(data[int(offsets[j])-origin:int(offsets[j+1])-origin]);b=chess.Board(fen);assert b.is_valid(),fen
                f.write(json.dumps(dict(fen=fen,win_probability=p,record_index=entry['first_record']+j,block=i))+'\n');valid+=1
        entry['valid_records']=valid
    (dest/'manifest.json').write_text(json.dumps(dict(plan=plan,blocks=blocks,total_download_bytes=sum(b['bytes']+80008 for b in blocks)+8,seconds=time.perf_counter()-started),indent=2))
    print(json.dumps(dict(records=200000,decoded=180000,sealed=20000,bytes=sum(b['bytes']+80008 for b in blocks)+8,seconds=time.perf_counter()-started)),flush=True)
if __name__=='__main__':main()
