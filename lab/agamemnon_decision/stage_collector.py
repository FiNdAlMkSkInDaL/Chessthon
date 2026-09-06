"""Track exact leaf provenance through the existing search, without changing scores."""
import hashlib,json,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
HELPERS='''@njit(cache=False)
def provenance_leaf(bb,st,ply,score,trace):
    if not trace[2,0] or ply>=MAX_PLY:return
    row=3+4*ply
    for p in range(12):
        trace[row,2*p]=np.int32(bb[p]&np.uint64(0xffffffff))
        trace[row,2*p+1]=np.int32(bb[p]>>np.uint64(32))
    for j,index in enumerate((SIDE,CASTLE,EP,FIFTY,FULL)):trace[row,24+j]=np.int32(st[index])
    trace[row,29]=score;trace[row,30]=1;trace[row,31]=0

@njit(cache=False)
def provenance_move(ply,move,trace):
    if not trace[2,0] or ply>=MAX_PLY:return
    row=3+4*ply;child=row+4
    for i in range(4):
        for j in range(32):trace[row+i,j]=trace[child+i,j]
    count=trace[row,31]
    if not trace[row,30] or count>=95:
        trace[row,30]=0;return
    for i in range(count-1,-1,-1):trace[row+1+(i+1)//32,(i+1)%32]=trace[row+1+i//32,i%32]
    trace[row+1,0]=move;trace[row,31]=count+1

'''
def main():
    dest=HERE/'collector';dest.mkdir(exist_ok=False)
    for p in (ROOT/'lab/agamemnon_scale/frontier/native/mix50').iterdir():
        if p.suffix in ('.py','.npz'):shutil.copyfile(p,dest/p.name)
    p=dest/'core_nb.py';s=p.read_text();needle='NN_ACC = np.tile(NET[768].astype(np.int32), (2,1))';assert needle in s;s=s.replace(needle,needle+'\nNN_ACC = np.concatenate([NN_ACC,np.zeros((395,32),np.int32)])')
    start=s.index('@njit(cache=False)\ndef qsearch_nb(');s=s[:start]+HELPERS+s[start:]
    for name,nextname in [('qsearch_nb','negamax_nb'),('negamax_nb','root_search_nb')]:
        start=s.index('def '+name+'(');end=s.index('def '+nextname+'(',start);body=s[start:end]
        old='    nodes[0] += 1';assert body.count(old)==1;body=body.replace(old,'    if nn_acc[2,0] and ply<=MAX_PLY:nn_acc[3+4*ply,30]=0\n'+old)
        old='        if score > best:\n            best = score';assert body.count(old)==1;body=body.replace(old,'        if score > best:\n            provenance_move(ply,move,nn_acc)\n            best = score')
        if name=='qsearch_nb':
            old='        stand = evaluate_nb(bb, st, adjudicate, net, nn_last, nn_acc)';assert body.count(old)==1;body=body.replace(old,old+'\n        provenance_leaf(bb,st,ply,stand,nn_acc)')
        s=s[:start]+body+s[end:]
    start=s.index('def root_search_nb(');end=s.index('def pack_pos(',start);body=s[start:end];body=body.replace('    moves = stacks[0]','    if nn_acc[2,0]:nn_acc[3,30]=0\n    moves = stacks[0]');body=body.replace('        if score > best_score:\n','        if score > best_score:\n            provenance_move(0,move,nn_acc)\n');s=s[:start]+body+s[end:];p.write_text(s)
    (HERE/'collector-manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir()},indent=2))
if __name__=='__main__':main()
