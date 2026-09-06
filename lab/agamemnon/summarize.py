"""Audit complete experiment streams and emit reproducible aggregate evidence."""
import collections,datetime,hashlib,json,math
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def read(p):return [json.loads(l) for l in p.open()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),experiments={})
    for group,expected in [('screen',60),('public-screen',24),('transfer-screen',16)]:
        streams=sorted((HERE/group).glob('*/results.jsonl'));trials=[]
        assert len(streams)==4
        for p in streams:
            rows=read(p);assert rows[0]['type']=='metadata' and rows[-1]['type']=='complete',p
            trials.extend(r for r in rows if r['type']=='trial')
        assert len(trials)==expected
        grouped=collections.defaultdict(list)
        for r in trials:
            key=(r['name'],r.get('fraction',r.get('cap',r.get('initialization'))));grouped[key].append(r)
        summary=[]
        for (name,setting),items in sorted(grouped.items()):
            summary.append(dict(name=name,setting=setting,seeds=len(items),development_mae_mean=float(np.mean([r['metrics']['development']['model']['mae'] for r in items])),epochs_selected=[r['selected_epoch'] for r in items],seconds=sum(r['seconds'] for r in items)))
        result['experiments'][group]=dict(trials=len(trials),summary=summary,streams={str(p.relative_to(HERE)):sha(p) for p in streams})
    result['total_training_fits']=100
    timings=[];native={}
    for suffix in ('','-swapped'):
        datasets={}
        for variant in ('delta','quant_refresh'):
            p=HERE/f'{variant}{suffix}-linux.jsonl';rows=read(p);assert rows[-1]['type']=='complete'
            native[p.name]=dict(cold_seconds=rows[0]['cold_seconds'],checks=next(r for r in rows if r['type']=='checks'),sha256=sha(p))
            datasets[variant]={(r['id'],r['budget'],r['kind']):r for r in rows if r['type']=='probe'}
        for key,r in datasets['delta'].items():
            if key[2]!='nodes':continue
            other=datasets['quant_refresh'][key]
            identity=lambda q:(q['uci'],q['info']['nodes'],q['info']['score'],q['info']['depth'])
            assert identity(r)==identity(other),(suffix,key)
            timings.append(dict(pass_name=suffix or 'initial',id=key[0],budget=key[1],delta_seconds=r['seconds'],refresh_seconds=other['seconds'],speed_ratio=other['seconds']/r['seconds']))
    result['native']=dict(streams=native,fixed_node_identical_comparisons=len(timings),timings=timings,geometric_speed_ratio=float(np.exp(np.mean([np.log(t['speed_ratio']) for t in timings]))),scope='Same quantized model/tree; two runs with CPU assignments swapped. Six USED roots, not general search speed or Elo. Fresh process/JIT each pass.')
    result['public_data']=json.loads((HERE/'public-data/manifest.json').read_text())
    result['public_fetch']=json.loads((HERE/'chessbench/manifest.json').read_text())['total_download_bytes']
    result['quantization']=json.loads((HERE/'native-delta-r1/manifest.json').read_text())['quantization']
    archive=HERE.parents[1].parent/'agent.zip';result['desktop_archive']=dict(path=str(archive),sha256=sha(archive),unchanged_tempest=sha(archive)=='0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4')
    assert result['desktop_archive']['unchanged_tempest']
    result['scope']='Architecture development only. No new competition upload, release zip, full-clock strength match, or independent promotion decision. Existing fresh confirmation games unplayed; public blocks18/19 not decoded.'
    (HERE/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(fits=100,fixed_node_identity=len(timings),speed_ratio=result['native']['geometric_speed_ratio'],desktop_unchanged=True)))
if __name__=='__main__':main()
