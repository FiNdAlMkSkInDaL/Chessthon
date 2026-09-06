"""Deduplicate legal sampler states and label disjoint shards offline."""
import argparse,collections,hashlib,json,os,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
import chess,chess.engine
from review_v6_games import reference,EXE,sha
from lab.laptop_runner import apply_windows_affinity
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--shard',type=int,default=0);ap.add_argument('--shards',type=int,default=4);ap.add_argument('--cpu',type=int,default=4);a=ap.parse_args()
    if a.prepare:
        samples=[]
        for line in (HERE/'data/search-states.jsonl').open():
            r=json.loads(line)
            if r.get('type')=='root':samples.extend(r['samples'])
        groups=collections.defaultdict(list)
        for s in samples:groups[' '.join(chess.Board(s['fen']).fen(en_passant='legal').split()[:4])].append(s)
        selected=[];collisions=0
        for k,rows in groups.items():
            if len({r['split'] for r in rows})>1:collisions+=1;continue
            r=min(rows,key=lambda r:r['id']);selected.append(r)
        selected.sort(key=lambda r:r['id'])
        out=HERE/'data/states.jsonl';out.write_text(''.join(json.dumps(r)+'\n' for r in selected))
        report=dict(raw=len(samples),deduplicated=len(selected),cross_split_positions_removed=collisions,split_counts=dict(collections.Counter(r['split'] for r in selected)),kind_counts=dict(collections.Counter(r['kind'] for r in selected)),sha256=sha(out),nodes_per_label=200000,shards=a.shards,scope='History-preserving deeper leaf labels; root ranking requires a separate search gate, not static one-ply substitutes.')
        (HERE/'data/labels-plan.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));return
    if os.name=='nt':assert apply_windows_affinity(a.cpu)['applied']
    else:os.sched_setaffinity(0,{a.cpu})
    states=[json.loads(s) for s in (HERE/'data/states.jsonl').read_text().splitlines()]
    with chess.engine.SimpleEngine.popen_uci(str(EXE)) as e,(HERE/f'data/labels-{a.shard}.jsonl').open('x') as out:
        e.configure({'Threads':1,'Hash':64,'UCI_ShowWDL':True});start=time.perf_counter()
        def emit(r):out.write(json.dumps(r)+'\n');out.flush()
        emit(dict(type='metadata',shard=a.shard,shards=a.shards,states_sha256=sha(HERE/'data/states.jsonl'),reference_sha256=sha(EXE),script_sha256=sha(Path(__file__)),nodes=200000))
        count=0
        for i,r in enumerate(states):
            if i%a.shards!=a.shard:continue
            b=chess.Board(r['start_fen'])
            for u in r['history_uci']:b.push_uci(u)
            assert b.fen()==r['fen']
            ref=reference(e,b,200000)
            emit(dict(type='label',id=r['id'],reference=ref));count+=1
            if count%200==0:print(a.shard,count,round(time.perf_counter()-start,1),flush=True)
        emit(dict(type='complete',count=count,seconds=time.perf_counter()-start))
if __name__=='__main__':main()
