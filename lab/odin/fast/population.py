"""Amortize baseline compilation across a scheduled generation lane."""
import argparse,json,sys,time,hashlib
from pathlib import Path
import chess,chess.pgn
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.odin.fast.match import Worker
ap=argparse.ArgumentParser();ap.add_argument('--lane',required=True);ap.add_argument('--cpu',type=int,required=True);ap.add_argument('--policy',type=Path,required=True);ap.add_argument('--openings',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--nodes',type=int,default=20000);args=ap.parse_args()
policy=json.loads(args.policy.read_text());jobs=[r for r in policy['generation'] if r['lane']==args.lane];assert jobs
fens=args.openings.read_text().splitlines();args.output.mkdir(parents=True,exist_ok=True)
baseline=Worker(ROOT/'odin_submission',args.cpu,args.nodes,args.output/(args.lane+'.baseline.stderr'))
baseline_proof=baseline.request({'cmd':'selftest'});assert baseline_proof['pass']
try:
    for job in jobs:
        source=ROOT/job['source'];candidate=None;began=time.monotonic();games=[]
        with (args.output/(job['name']+'.jsonl')).open('x',encoding='utf-8') as out:
            def emit(row):out.write(json.dumps(row,allow_nan=False)+'\n');out.flush()
            emit({'type':'plan','candidate':job['name'],'candidate_source':job['source'],'baseline':'odin_submission','cpu':args.cpu,'node_limit':args.nodes,
                  'indices':list(range(len(fens))),'openings_sha256':hashlib.sha256(args.openings.read_bytes()).hexdigest(),'policy_sha256':hashlib.sha256(args.policy.read_bytes()).hexdigest(),
                  'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'lane':args.lane})
            try:
                candidate=Worker(source,args.cpu,args.nodes,args.output/(job['name']+'.candidate.stderr'))
                assert candidate.ready['source_hashes']==job['hashes']
                proof=candidate.request({'cmd':'selftest'});assert proof['pass']
                emit({'type':'worker','role':'baseline','metadata':baseline.ready,'isolation':baseline_proof})
                emit({'type':'worker','role':'candidate','metadata':candidate.ready,'isolation':proof})
                print(json.dumps({'event':'CANDIDATE_READY','name':job['name'],'cold_s':candidate.ready['cold_seconds']}),flush=True)
                for index,fen in enumerate(fens):
                    for color in (chess.WHITE,chess.BLACK):
                        baseline.request({'cmd':'reset'});candidate.request({'cmd':'reset'})
                        b=chess.Board(fen);g=chess.pgn.Game();g.setup(b);node=g;telemetry=[];start=time.monotonic()
                        g.headers.update(White=job['name'] if color else 'odin_v5',Black='odin_v5' if color else job['name'])
                        while True:
                            outcome=b.outcome(claim_draw=True)
                            if outcome is not None:result=outcome.result();termination=outcome.termination.name;break
                            if b.ply()>=600:result='1/2-1/2';termination='PLY_CAP';break
                            role='candidate' if b.turn==color else 'baseline';w=candidate if role=='candidate' else baseline
                            answer=w.request({'cmd':'move','fen':b.fen()});move=chess.Move.from_uci(answer['uci']);assert move in b.legal_moves
                            telemetry.append(dict(role=role,**answer));b.push(move);node=node.add_variation(move)
                        points=.5 if result=='1/2-1/2' else float((result=='1-0')==color)
                        g.headers.update(Result=result,Termination=termination)
                        row={'type':'game','game':len(games)+1,'opening_index':index,'candidate_colour':'white' if color else 'black','candidate_points':points,
                             'result':result,'termination':termination,'pgn':str(g),'seconds':time.monotonic()-start,'plies':len(telemetry),'telemetry':telemetry}
                        games.append(row);emit(row)
                summary={'type':'summary','candidate':job['name'],'games':len(games),'points':sum(g['candidate_points'] for g in games),'score':sum(g['candidate_points'] for g in games)/len(games),'seconds':time.monotonic()-began}
                emit(summary);print(json.dumps(summary),flush=True)
            except BaseException as exc:
                emit({'type':'error','error':type(exc).__name__+': '+str(exc)});raise
            finally:
                if candidate:candidate.close()
finally:baseline.close()
