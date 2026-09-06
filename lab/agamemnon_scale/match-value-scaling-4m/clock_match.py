"""Paired fixed-node games with persistent audited workers, one active mover/core."""
import argparse,json,os,queue,subprocess,sys,threading,time,hashlib
from pathlib import Path
import chess,chess.pgn
ROOT=Path(__file__).resolve().parents[3]

class Worker:
    def __init__(self,source,cpu,nodes,stderr):
        self.err=open(stderr,'w',encoding='utf-8')
        self.p=subprocess.Popen([sys.executable,'-B','-u',str(Path(__file__).with_name('clock_worker.py')),'--source',str(source),'--cpu',str(cpu),'--nodes',str(nodes)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
        self.q=queue.Queue()
        def reader():
            for line in self.p.stdout:self.q.put(line)
            self.q.put(None)
        threading.Thread(target=reader,daemon=True).start()
        self.ready=self.read(300)
        assert self.ready.get('event')=='READY',self.ready
    def read(self,timeout=60):
        line=self.q.get(timeout=timeout)
        if line is None:raise RuntimeError('Worker exited; inspect worker stderr')
        value=json.loads(line)
        if 'error' in value:raise RuntimeError(value['error'])
        return value
    def request(self,command):
        self.p.stdin.write(json.dumps(command)+'\n');self.p.stdin.flush();return self.read()
    def close(self):
        if self.p.poll() is None:
            try:self.p.stdin.write('{"cmd":"quit"}\n');self.p.stdin.flush();self.p.wait(timeout=10)
            except Exception:self.p.kill();self.p.wait()
        self.err.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--cpu',type=int,required=True);ap.add_argument('--nodes',type=int,default=20000);ap.add_argument('--openings',type=Path,required=True)
    ap.add_argument('--think-ms',type=int,default=100);ap.add_argument('--indices',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    indices=[int(s) for s in args.indices.split(',')]
    fens=[s for s in args.openings.read_text().splitlines() if s.strip() and not s.startswith('#')]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    workers={};began=time.monotonic();games=[]
    with args.output.open('x',encoding='utf-8') as out:
        def emit(r):out.write(json.dumps(r,allow_nan=False)+'\n');out.flush()
        emit({'type':'plan','candidate':args.candidate.name,'baseline':args.baseline.name,'indices':indices,'isolation_node_limit':args.nodes,'think_ms':args.think_ms,'cpu':args.cpu,
              'openings_sha256':hashlib.sha256(args.openings.read_bytes()).hexdigest(),'policy':'Fixed search-time development screen: original clock driver, soft=90% hard per move, persistent fully reset agents. Equal CPU-affined think allowance; no competition game-clock claim. Complete all declared pairs without result-dependent stopping. Current600-ply referee outcomes; Current official commit284724a. Twelve fixed short-wall smoke games; not a full-clock Elo estimate.'})
        try:
            for role,source in [('baseline',args.baseline),('candidate',args.candidate)]:
                workers[role]=Worker(source.resolve(),args.cpu,args.nodes,args.output.with_suffix('.'+role+'.stderr'))
                proof=workers[role].request({'cmd':'selftest'})
                assert proof['pass']
                mode=workers[role].request({'cmd':'clock_mode','hard_ms':args.think_ms,'soft_ms':args.think_ms*.9});assert mode['clock_mode']
                emit({'type':'clock_mode','role':role,**mode})
                emit({'type':'worker','role':role,'metadata':workers[role].ready,'isolation':proof})
                print(json.dumps({'event':'WARM_WORKER_READY','role':role,'cpu':args.cpu,'cold_s':workers[role].ready['cold_seconds'],'reset_s':proof['reset_seconds']}),flush=True)
            for pair,index in enumerate(indices):
                for color in (chess.WHITE,chess.BLACK):
                    for w in workers.values():w.request({'cmd':'reset'})
                    b=chess.Board(fens[index]);g=chess.pgn.Game();g.setup(b)
                    g.headers.update(White=args.candidate.name if color else args.baseline.name,Black=args.baseline.name if color else args.candidate.name)
                    node=g;telemetry=[];start=time.monotonic()
                    while True:
                        outcome=b.outcome()
                        if outcome is None and b.is_repetition(3):outcome=chess.Outcome(chess.Termination.THREEFOLD_REPETITION,None)
                        if outcome is None and b.is_fifty_moves():outcome=chess.Outcome(chess.Termination.FIFTY_MOVES,None)
                        if outcome is not None:
                            result=outcome.result();termination=outcome.termination.name;break
                        if b.ply()>=600:result='1/2-1/2';termination='PLY_CAP';break
                        role='candidate' if b.turn==color else 'baseline'
                        answer=workers[role].request({'cmd':'move','fen':b.fen()})
                        move=chess.Move.from_uci(answer['uci']);assert move in b.legal_moves
                        telemetry.append(dict(role=role,**answer));b.push(move);node=node.add_variation(move)
                    points=.5 if result=='1/2-1/2' else float((result=='1-0')==color)
                    g.headers['Result']=result;g.headers['Termination']=termination
                    row={'type':'game','game':len(games)+1,'opening_index':index,'candidate_colour':'white' if color else 'black','candidate_points':points,
                         'result':result,'termination':termination,'pgn':str(g),'seconds':time.monotonic()-start,'plies':len(telemetry),'telemetry':telemetry}
                    games.append(row);emit(row)
                    print(json.dumps({'game':len(games),'index':index,'points':points,'seconds':round(row['seconds'],2),'plies':row['plies']}),flush=True)
            emit({'type':'summary','games':len(games),'score':sum(g['candidate_points'] for g in games)/len(games),'seconds':time.monotonic()-began})
        finally:
            for w in workers.values():w.close()

if __name__=='__main__':main()
