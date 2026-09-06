"""Paired whole-search equivalence/throughput; same nodes, alternating order."""
import argparse,json,sys,statistics,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from lab.odin.fast.match import Worker
ap=argparse.ArgumentParser();ap.add_argument('--cpu',type=int,default=8);ap.add_argument('--baseline',default='odin_submission');ap.add_argument('--candidate',default='odin_fused');ap.add_argument('--output',type=Path,default=HERE/'fused-search-benchmark.json');ap.add_argument('--nodes',type=int,default=100000);ap.add_argument('--mixed',action='store_true');args=ap.parse_args()
workers={};rows=[]
fens=(HERE/'generation-openings/screen.fen').read_text().splitlines()+(HERE/'generation-openings/confirm.fen').read_text().splitlines()
if args.mixed:
    import chess
    label_rows=[json.loads(s) for s in (ROOT/'lab/odin/quiet_eval/fit-records.jsonl').read_text().splitlines()]
    fens=fens[::3]+[r['fen'] for r in label_rows[::199] if not chess.Board(r['fen']).is_game_over(claim_draw=True)]
raw=args.output.with_suffix('.jsonl').open('x',encoding='utf-8')
try:
    for name,source in [('baseline',args.baseline),('fused',args.candidate)]:
        workers[name]=Worker(ROOT/source,args.cpu,args.nodes,args.output.with_name(args.output.stem+'-'+name+'.stderr'))
        assert workers[name].request({'cmd':'selftest'})['pass']
        raw.write(json.dumps({'type':'worker','role':name,'metadata':workers[name].ready})+'\n');raw.flush()
    for i,fen in enumerate(fens):
        row={'index':i,'fen':fen}
        for name in (('baseline','fused') if i%2==0 else ('fused','baseline')):
            workers[name].request({'cmd':'reset'});row[name]=workers[name].request({'cmd':'move','fen':fen})
        assert all(row['baseline'][k]==row['fused'][k] for k in ('uci','depth','score','nodes')),row
        rows.append(row)
        raw.write(json.dumps({'type':'position',**row})+'\n');raw.flush()
        if (i+1)%10==0:print(json.dumps({'positions_complete':i+1,'planned':len(fens)}),flush=True)
    base=sum(r['baseline']['seconds'] for r in rows);fused=sum(r['fused']['seconds'] for r in rows)
    result={'pass':True,'positions':len(rows),'nodes_per_position':args.nodes,'total_baseline_seconds':base,'total_fused_seconds':fused,'throughput_ratio':base/fused,
            'metadata':{k:w.ready for k,w in workers.items()},'rows':rows,'platform':platform.platform(),'scope':'Whole-search comparison on the recorded host; all selected moves, scores, depths and node counts equal. Native exact-source gate still required for a submission.'}
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('metadata','rows')}))
finally:
    raw.close()
    for w in workers.values():w.close()
