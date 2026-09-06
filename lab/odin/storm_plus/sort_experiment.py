"""Measure a stable, lexicographically identical one-key insertion sort."""
import ast
import json
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[3]

REPLACEMENT='''@njit(cache=False)
def sort_moves(mb, moves, n, ply, hash_move, killers, histy):
    if n <= 1:
        return
    keys = np.empty(n, dtype=np.int64)
    for i in range(n):
        a, b = order_key(mb, moves[i], ply, hash_move, killers, histy)
        keys[i] = np.int64(a) * np.int64(4294967296) + np.int64(b)
    for i in range(1, n):
        mv = moves[i]
        key = keys[i]
        j = i
        while j > 0 and keys[j-1] > key:
            moves[j] = moves[j-1]
            keys[j] = keys[j-1]
            j -= 1
        moves[j] = mv
        keys[j] = key
'''


def main():
    import ctypes
    k=ctypes.windll.kernel32
    k.GetCurrentProcess.restype=ctypes.c_void_p
    k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    assert k.SetProcessAffinityMask(k.GetCurrentProcess(),1<<7)
    sys.path.insert(0,str(ROOT/'odin_storm_plus'))
    import core_nb as core
    import numpy as np
    import chess
    from board_nb import from_fen
    from movegen_nb import generate_legal
    from numba import njit
    namespace=dict(vars(core))
    exec(compile(REPLACEMENT,'stable_combined_sort.py','exec'),namespace)
    new=namespace['sort_moves']
    rng=random.Random(2026090507)
    board=chess.Board()
    cases=[]
    for i in range(1000):
        if board.is_game_over() or i%100==0:board=chess.Board()
        pos=from_fen(board.fen())
        bb,mb,st=core.pack_pos(pos)
        moves=np.array(generate_legal(pos),np.int32)
        rng.shuffle(moves)
        killer=np.zeros((96,2),np.int32)
        history=np.array([rng.randint(-16384,16384) for _ in range(768)],np.int32).reshape(12,64)
        ply=rng.randrange(96)
        if len(moves):killer[ply]=[rng.choice(moves),rng.choice(moves)]
        hash_move=int(rng.choice(moves)) if len(moves) and i%3 else 0
        old_sorted=moves.copy();new_sorted=moves.copy()
        core.sort_moves(mb,old_sorted,len(moves),ply,hash_move,killer,history)
        new(mb,new_sorted,len(moves),ply,hash_move,killer,history)
        assert np.array_equal(old_sorted,new_sorted),(board.fen(),i)
        if i%10==0:cases.append((mb,moves,ply,hash_move,killer,history))
        if board.legal_moves:board.push(rng.choice(list(board.legal_moves)))
    old=core.sort_moves
    @njit
    def benchmark(mb,moves,ply,hash_move,killer,history,repetitions,optimized):
        answer=0
        for _ in range(repetitions):
            trial=moves.copy()
            if optimized:new(mb,trial,len(trial),ply,hash_move,killer,history)
            else:old(mb,trial,len(trial),ply,hash_move,killer,history)
            if len(trial):answer+=trial[0]
        return answer
    benchmark(*cases[0],1,False)
    timings={}
    for optimized in (False,True):
        began=time.perf_counter()
        for c in cases:benchmark(*c,5000,optimized)
        timings[str(optimized)]=time.perf_counter()-began
    result={'identical_legal_position_orderings':1000,'seconds_per_500000_sorts':timings,
            'relative_time':timings['True']/timings['False'],
            'scope':'Laptop microbenchmark only. Does not establish search throughput, cold Linux cost or Elo.'}
    (Path(__file__).parent/'sort-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
