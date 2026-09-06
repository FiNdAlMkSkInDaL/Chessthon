"""No-JIT regression for mandatory native entry despite arbitrary setup delay."""
import ast
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'odin_release_candidate/core_nb.py'


def warmup_namespace(compiles=True,clock_aborts=True):
    tree=ast.parse(SOURCE.read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='warmup')
    pos=types.SimpleNamespace()
    board=types.ModuleType('board_nb')
    board.START_FEN='fixture'
    board.from_fen=lambda fen:pos
    movegen=types.ModuleType('movegen_nb')
    movegen.generate_legal=lambda p:[1,2]
    timeline=[0.0,900.0]
    calls=[]
    class NativeRoot:
        nopython_signatures=[]
        def __call__(self,*args):
            calls.append(args)
            if compiles:
                self.nopython_signatures=['live-signature']
            return 1,0
    native=NativeRoot()
    def clock(nodes,max_nodes,allow,aborted):
        assert nodes.dtype==np.int64 and nodes.tolist()==[1024,1]
        assert allow is True
        aborted[0]=int(clock_aborts)
        return clock_aborts
    namespace={'np':np,'time':types.SimpleNamespace(perf_counter=lambda:timeline.pop(0)),
               'NUMBA_READY':True,'WARMUP_S':0.,'perft_pos':lambda *args:400,
               'pack_pos':lambda _: (np.zeros(12,np.uint64),np.zeros(64,np.int8),np.zeros(12,np.uint64)),
               'MAX_PLY':96,'MAX_MOVES':256,'KEY':8,'HIST_SEED':np.uint64(123),
               'history_has_pair':lambda *args:False,'history_append':lambda *args:np.uint64(5),
               'move_hint_probe':lambda *args:0,'check_clock':clock,
               'root_search_nb':native,'INF':32001,
               'search_root':lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('Live deadline controller entered'))}
    for name,dtype in [('TT_KEY',np.uint64),('TT_MOVE',np.int32),('TT_SCORE',np.int16),
                       ('TT_DEPTH',np.uint8),('TT_GEN',np.uint8),('TT_AGE',np.int32),
                       ('KILLERS',np.int32),('HISTORY',np.int32)]:
        namespace[name]=np.zeros(2,dtype)
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(SOURCE),'exec'),namespace)
    return namespace,calls,{'board_nb':board,'movegen_nb':movegen}


class WarmupTests(unittest.TestCase):
    def test_arbitrarily_slow_setup_cannot_skip_native_root(self):
        ns,calls,modules=warmup_namespace()
        with patch.dict(sys.modules,modules):
            self.assertTrue(ns['warmup']())
        self.assertEqual(len(calls),1)
        self.assertEqual(ns['WARMUP_S'],900.)
        self.assertTrue(ns['NUMBA_READY'])
        args=calls[0]
        self.assertEqual(args[3].dtype,np.int32)
        self.assertEqual(args[6].dtype,np.uint64)
        self.assertIs(type(args[14]),np.uint64)
        self.assertEqual(args[-2].dtype,np.int64)
        self.assertEqual(args[-2].tolist(),[0,0])
        self.assertEqual(args[-1].dtype,np.int32)
        self.assertEqual(args[5],1)

    def test_empty_signature_cannot_report_ready(self):
        ns,calls,modules=warmup_namespace(compiles=False)
        with patch.dict(sys.modules,modules):
            with self.assertRaisesRegex(RuntimeError,'not compiled'):
                ns['warmup']()
        self.assertFalse(ns['NUMBA_READY'])
        self.assertEqual(len(calls),1)

    def test_failed_expired_clock_cannot_report_ready(self):
        ns,calls,modules=warmup_namespace(clock_aborts=False)
        with patch.dict(sys.modules,modules):
            with self.assertRaisesRegex(RuntimeError,'clock'):
                ns['warmup']()
        self.assertFalse(ns['NUMBA_READY'])
        self.assertEqual(calls,[])


if __name__=='__main__':
    unittest.main()
