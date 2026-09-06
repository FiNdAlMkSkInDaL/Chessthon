"""Offline persistent node-budget worker. Never packaged with the engine.

Runs the actual agent entrypoint and actual native search, with two explicitly
logged Python-driver substitutions: no wall deadline and a fixed node cap.
All source-module mutable data/scalars and fallback TT are restored per game.
"""
import argparse,copy,hashlib,inspect,json,os,platform,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--cpu',type=int,required=True);ap.add_argument('--nodes',type=int,default=40000)
args=ap.parse_args()
for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):os.environ[name]='1'
sys.dont_write_bytecode=True
if os.name=='nt':
    from lab.laptop_runner import apply_windows_affinity,apply_windows_memory_job
    assert apply_windows_affinity(args.cpu)['applied']
    assert apply_windows_memory_job(2*1024**3)['applied']
else:os.sched_setaffinity(0,{args.cpu})
source=args.source.resolve()
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(list(source.glob('*.py'))+list(source.glob('*.npz')))}
sys.path.insert(0,str(source));began=time.perf_counter()
import agent,core_nb as core,tt_nb
import numpy as np
import chess
cold=time.perf_counter()-began
assert core.NUMBA_READY and core.root_search_nb.nopython_signatures
original_driver=core.search_root
clock_settings=None
original=inspect.getsource(core.search_root)
deadline='nodes[1] = int((start + hard_ms / 1000.0) * 1_000_000_000)'
limit='max_nodes = 10**15  # deadline inside compiled search is authoritative'
assert original.count(deadline)==1 and original.count(limit)==1
instrumented=original.replace(deadline,'nodes[1] = 0  # LAB fixed-node mode').replace(limit,'max_nodes = _LAB_NODE_LIMIT')
core._LAB_NODE_LIMIT=args.nodes
exec(compile(instrumented,'<lab-fixed-node-driver>','exec'),core.__dict__)
driver=core.search_root
native_call={'count':0,'error':None}
def fixed_nodes(pos,packed_root,hard_ms,soft_ms,adjudicate,game_zkeys):
    native_call['count']+=1
    try:
        if clock_settings is not None:
            return original_driver(pos,packed_root,clock_settings[0],clock_settings[1],adjudicate,game_zkeys)
        return driver(pos,packed_root,1e12,1e12,adjudicate,game_zkeys)
    except Exception as exc:
        native_call['error']=type(exc).__name__+': '+str(exc)
        raise
core.search_root=fixed_nodes

modules=[m for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).resolve().parent==source]
snapshot=[]
for mod in modules:
    for name,value in list(vars(mod).items()):
        if name.startswith('__'):continue
        if isinstance(value,np.ndarray):snapshot.append((mod,name,'array',value.copy()))
        elif isinstance(value,(dict,list,set,bytearray)) or value is None or isinstance(value,(str,int,float,bool,np.generic)):
            snapshot.append((mod,name,'value',copy.deepcopy(value)))
tt_snapshot=(bytes(tt_nb.tt.data),tt_nb.tt.age)
signatures=list(map(str,core.root_search_nb.nopython_signatures))

def reset():
    began=time.perf_counter()
    for mod,name,kind,saved in snapshot:
        if kind=='array':
            current=getattr(mod,name)
            if current.flags.writeable:np.copyto(current,saved)
            else:assert np.array_equal(current,saved), 'Immutable module array changed'
        else:setattr(mod,name,copy.deepcopy(saved))
    tt_nb.tt.data[:]=tt_snapshot[0];tt_nb.tt.age=tt_snapshot[1]
    assert core.NUMBA_READY
    return time.perf_counter()-began

def move(fen):
    b=chess.Board(fen);assert b.is_valid() and b.outcome() is None and not b.is_repetition(3) and not b.is_fifty_moves()
    native_call.update(count=0,error=None)
    began=time.perf_counter();uci=agent.get_move(fen,120000);elapsed=time.perf_counter()-began
    assert chess.Move.from_uci(uci) in b.legal_moves
    assert native_call['error'] is None,native_call
    exact_module=sys.modules.get('endgame_exact')
    exact_route=bool(exact_module is not None and exact_module.choose_exact(b) is not None)
    assert native_call['count']==int(b.legal_moves.count()>1 and not exact_route),('Unexpected fallback',fen,native_call)
    info=core.last_info() if native_call['count'] else {'depth':0,'score':0,'nodes':0}
    assert list(map(str,core.root_search_nb.nopython_signatures))==signatures,'Deferred root compilation'
    return {'route':'exact' if exact_route else 'search' if native_call['count'] else 'forced','uci':uci,'depth':info['depth'],'score':info['score'],'nodes':info['nodes'],'seconds':elapsed}

def selftest():
    a='r1bq1rk1/pp3ppp/2nbpn2/1Bpp4/3P1B2/2P1P2N/PP1N1PPP/R2QK2R w KQ - 4 8'
    reset();first=move(a)
    b=chess.Board();
    for _ in range(6):b.push_uci(move(b.fen())['uci'])
    reset_s=reset();again=move(a)
    keys=('uci','depth','score','nodes')
    assert all(first[k]==again[k] for k in keys),(first,again)
    reset()
    return {'pass':True,'first':first,'after_unrelated_game_reset':again,'reset_seconds':reset_s,'restored_fields':len(snapshot),'method':'A-B-A deterministic node-budget isolation; all source-module data/scalars plus fallback TT restored.'}

def emit(value):print(json.dumps(value,allow_nan=False),flush=True)
emit({'event':'READY','source':source.name,'source_hashes':hashes,'cold_seconds':cold,'node_limit':args.nodes,'runtime':platform.platform(),'cpu':args.cpu,
      'worker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'silent_native_fallback_rejected':True,
      'instrumentation_sha256':hashlib.sha256(instrumented.encode()).hexdigest(),'readiness_override':False,'scope':'Offline strength screen, not competition wall-clock or init evidence.'})
for line in sys.stdin:
    try:
        cmd=json.loads(line)
        if cmd['cmd']=='selftest':emit(selftest())
        elif cmd['cmd']=='clock_mode':
            assert clock_settings is None
            assert 10 <= cmd['soft_ms'] <= cmd['hard_ms'] <= 1000
            clock_settings=(cmd['hard_ms'],cmd['soft_ms'])
            emit({'clock_mode':True,'hard_ms':clock_settings[0],'soft_ms':clock_settings[1],'driver':'Unmodified original source wall-clock root driver'})
        elif cmd['cmd']=='reset':emit({'reset_seconds':reset()})
        elif cmd['cmd']=='move':emit(move(cmd['fen']))
        elif cmd['cmd']=='quit':break
        else:raise ValueError('Unknown command')
    except Exception as exc:
        emit({'error':type(exc).__name__+': '+str(exc)});raise
assert hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(list(source.glob('*.py'))+list(source.glob('*.npz')))}
