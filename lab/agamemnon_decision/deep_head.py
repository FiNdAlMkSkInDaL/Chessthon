"""Original residual nonlinear mover/opponent head; no external model or code."""
import numpy as np
from numba import njit
@njit
def forward(x,counts,phase,turn,w,bias,out,u,b2,v):
    result=np.zeros(len(x),np.float32);h=w.shape[1];n=u.shape[1];act=np.empty(2*h,np.float32);z=np.empty(n,np.float32)
    for i in range(len(x)):
        value=0.
        for view in range(2):
            role=0 if (view==0)==(turn[i]==1) else 1
            for j in range(h):act[role*h+j]=bias[j]
            for k in range(counts[i,view]):
                for j in range(h):act[role*h+j]+=w[x[i,view,k],j]
            for j in range(h):
                a=min(2.,max(0.,act[role*h+j]));act[role*h+j]=a;value+=a*(phase[i]*out[j,2*role]+(1-phase[i])*out[j,2*role+1])
        for k in range(n):z[k]=b2[k]
        for j in range(2*h):
            for k in range(n):z[k]+=act[j]*u[j,k]
        for k in range(n):value+=min(2.,max(0.,z[k]))*(phase[i]*v[k,0]+(1-phase[i])*v[k,1])
        result[i]=turn[i]*value
    return result

@njit
def grad(x,counts,phase,turn,y,weights,ids,w,bias,out,u,b2,v):
    gw=np.zeros_like(w);gb=np.zeros_like(bias);go=np.zeros_like(out);gu=np.zeros_like(u);gb2=np.zeros_like(b2);gv=np.zeros_like(v)
    h=w.shape[1];n=u.shape[1];sums=np.empty(2*h,np.float32);act=np.empty(2*h,np.float32);z=np.empty(n,np.float32);hidden=np.empty(n,np.float32);da=np.empty(2*h,np.float32);dz=np.empty(n,np.float32);total=0.;loss=0.
    for i in ids:total+=weights[i]
    for i in ids:
        pred=0.
        for view in range(2):
            role=0 if (view==0)==(turn[i]==1) else 1
            for j in range(h):sums[role*h+j]=bias[j]
            for k in range(counts[i,view]):
                for j in range(h):sums[role*h+j]+=w[x[i,view,k],j]
            for j in range(h):
                act[role*h+j]=min(2.,max(0.,sums[role*h+j]));pred+=act[role*h+j]*(phase[i]*out[j,role*2]+(1-phase[i])*out[j,role*2+1])
        for k in range(n):z[k]=b2[k]
        for j in range(2*h):
            for k in range(n):z[k]+=act[j]*u[j,k]
        for k in range(n):hidden[k]=min(2.,max(0.,z[k]));pred+=hidden[k]*(phase[i]*v[k,0]+(1-phase[i])*v[k,1])
        err=turn[i]*pred-y[i];weight=weights[i]/total;loss+=weight*(.5*err*err if abs(err)<=1 else abs(err)-.5);d=turn[i]*weight*min(1.,max(-1.,err))
        for k in range(n):
            gv[k,0]+=d*hidden[k]*phase[i];gv[k,1]+=d*hidden[k]*(1-phase[i]);dz[k]=d*(phase[i]*v[k,0]+(1-phase[i])*v[k,1]) if 0<z[k]<2 else 0.;gb2[k]+=dz[k]
        for j in range(2*h):
            role=j//h;jj=j%h;da[j]=d*(phase[i]*out[jj,2*role]+(1-phase[i])*out[jj,2*role+1]);go[jj,2*role]+=d*act[j]*phase[i];go[jj,2*role+1]+=d*act[j]*(1-phase[i])
            for k in range(n):gu[j,k]+=act[j]*dz[k];da[j]+=u[j,k]*dz[k]
            if sums[j]<=0 or sums[j]>=2:da[j]=0.
            gb[jj]+=da[j]
        for view in range(2):
            role=0 if (view==0)==(turn[i]==1) else 1
            for k in range(counts[i,view]):
                for j in range(h):gw[x[i,view,k],j]+=da[role*h+j]
    return loss,gw,gb,go,gu,gb2,gv

def initialize(par,seed):
    rng=np.random.default_rng(seed);return [p.copy() for p in par]+[rng.normal(0,.025,(64,16)).astype(np.float32),np.full(16,.2,np.float32),np.zeros((16,2),np.float32)]

def verify():
    rng=np.random.default_rng(1709);x=np.array([[[0,1],[2,3]],[[1,3],[0,2]]],np.int32);counts=np.full((2,2),2,np.int32);phase=np.array([.3,.8],np.float32);turn=np.array([1,-1],np.int8);y=np.array([.2,-.1],np.float32)
    par=[rng.normal(0,.02,(4,3)).astype(np.float32),np.full(3,.5,np.float32),rng.normal(0,.05,(3,4)).astype(np.float32),rng.normal(0,.04,(6,4)).astype(np.float32),np.full(4,.3,np.float32),rng.normal(0,.03,(4,2)).astype(np.float32)]
    args=(x,counts,phase,turn,y,np.ones(2,np.float32),np.arange(2));_,*g=grad(*args,*par);checked=0
    for pi,p in enumerate(par):
        for idx in np.ndindex(p.shape):
            old=p[idx];eps=.001;p[idx]=old+eps;up=grad(*args,*par)[0];p[idx]=old-eps;dn=grad(*args,*par)[0];p[idx]=old;assert abs((up-dn)/(2*eps)-g[pi][idx])<3e-5;checked+=1
    pred=forward(x,counts,phase,turn,*par);mirror=forward(x[:,::-1].copy(),counts[:,::-1].copy(),phase,-turn,*par);assert np.max(abs(pred+mirror))<1e-6
    return dict(gradient_checks=checked,colour_turn_symmetry=True)
