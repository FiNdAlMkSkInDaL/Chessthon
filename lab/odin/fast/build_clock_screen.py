"""Build an explicit fixed-search-time development screen from audited workers.

No engine source changes; isolation is checked in deterministic node mode,
then the unmodified original wall-clock root driver is used for timed play.
This is a development screen, not a substitute for the frozen 112-game match.
"""
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=(HERE/'worker.py').read_text()
s=s.replace('original=inspect.getsource(core.search_root)','original_driver=core.search_root\nclock_settings=None\noriginal=inspect.getsource(core.search_root)')
s=s.replace('    try:return driver(pos,packed_root,1e12,1e12,adjudicate,game_zkeys)',
'''    try:
        if clock_settings is not None:
            return original_driver(pos,packed_root,clock_settings[0],clock_settings[1],adjudicate,game_zkeys)
        return driver(pos,packed_root,1e12,1e12,adjudicate,game_zkeys)''')
s=s.replace("        elif cmd['cmd']=='reset':",'''        elif cmd['cmd']=='clock_mode':
            assert clock_settings is None
            assert 10 <= cmd['soft_ms'] <= cmd['hard_ms'] <= 1000
            clock_settings=(cmd['hard_ms'],cmd['soft_ms'])
            emit({'clock_mode':True,'hard_ms':clock_settings[0],'soft_ms':clock_settings[1],'driver':'Unmodified original source wall-clock root driver'})
        elif cmd['cmd']=='reset':''')
(HERE/'clock_worker.py').write_text(s,encoding='utf-8',newline='\n')
s=(HERE/'match.py').read_text().replace("with_name('worker.py')","with_name('clock_worker.py')")
s=s.replace("ap.add_argument('--indices',required=True);", "ap.add_argument('--think-ms',type=int,default=100);ap.add_argument('--indices',required=True);")
s=s.replace("'node_limit':args.nodes,'cpu':args.cpu,", "'isolation_node_limit':args.nodes,'think_ms':args.think_ms,'cpu':args.cpu,")
old="'policy':'Fixed pair coverage in this lane. Controller may stop at declared whole-screen checkpoints for clear futility; no confidence claim from a short screen. No game-result adjudication, current600 absolute-ply rule and true claimable draws.'"
new="'policy':'Fixed search-time development screen: original clock driver, soft=90% hard per move, persistent fully reset agents. Equal CPU-affined think allowance; no competition game-clock claim. Complete all declared pairs without result-dependent stopping. Current600-ply referee outcomes; frozen112 full-clock match remains final evidence.'"
assert old in s;s=s.replace(old,new)
old="                assert proof['pass']\n";assert s.count(old)==1
s=s.replace(old,old+"                mode=workers[role].request({'cmd':'clock_mode','hard_ms':args.think_ms,'soft_ms':args.think_ms*.9});assert mode['clock_mode']\n                emit({'type':'clock_mode','role':role,**mode})\n")
(HERE/'clock_match.py').write_text(s,encoding='utf-8',newline='\n')
print('Built explicitly labelled original-driver fixed-time screen; sources unchanged.')
