"""Fast pairwise conflict using the numba geometry kernel (0.48us) with shapely
fallback on 'uncertain' (0.  Verified against grader_conflict."""
import os, sys, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71"))
import numpy as np
import myalgorithm as M
from shapely.geometry import Polygon

def layers_arr_poly(d, bid, x, y, o):
    """Return (arrs, polys): per-layer contiguous numpy arrays AND shapely polys."""
    blk=M.Block(block_id=bid, block_data=d["blocks"][bid], x=int(x), y=int(y), orient_idx=int(o))
    arrs=[]; polys=[]
    for L in blk.layers_at_pos():
        a=np.ascontiguousarray(np.asarray(L, dtype=np.float64))
        arrs.append(a)
        polys.append(Polygon([(float(p[0]),float(p[1])) for p in L]) if len(L)>=3 else None)
    return arrs, polys

def _cl(ai, aj, pi, pj):
    """overlap of layer polygon (arr ai, poly pi) vs (aj, pj), matching grader area>0."""
    if ai is None or aj is None or len(ai)<3 or len(aj)<3: return False
    c=M._g_classify_pair(ai, aj)
    if c==1: return True
    if c==2: return False
    if pi is None or pj is None: return False
    return pi.intersection(pj).area > 0.0

def conflict(Aa, Ap, ea, xa, Ba, Bp, eb, xb):
    """Aa/Ap: A layer arrs/polys; Ba/Bp: B.  entry/exit ea,xa / eb,xb."""
    if not (ea < xb and eb < xa): return False
    Ka, Kb = len(Aa), len(Ba)
    for k in range(min(Ka,Kb)):
        if _cl(Aa[k],Ba[k],Ap[k],Bp[k]): return True           # resting j==k
    if ea >= eb:                                                # A descends thru B
        for k in range(Ka):
            for j in range(k+1,Kb):
                if _cl(Aa[k],Ba[j],Ap[k],Bp[j]): return True
    if eb >= ea:                                                # B descends thru A
        for k in range(Kb):
            for j in range(k+1,Ka):
                if _cl(Ba[k],Aa[j],Bp[k],Ap[j]): return True
    if xa <= xb:                                                # A ascends thru B
        for k in range(Ka):
            for j in range(k+1,Kb):
                if _cl(Aa[k],Ba[j],Ap[k],Bp[j]): return True
    if xb <= xa:                                                # B ascends thru A
        for k in range(Kb):
            for j in range(k+1,Ka):
                if _cl(Ba[k],Aa[j],Bp[k],Ap[j]): return True
    return False

if __name__=="__main__":
    # verify vs grader_conflict
    import json, random
    sys.path.insert(0, os.path.join(SP,"research"))
    import conflictgen as CG
    from utils import Bay
    def find(n):
        for sub in ("data/training_instances/train","data/train"):
            p=os.path.join(SP,sub,n+".json")
            if os.path.exists(p): return p
    for nm in ["prob_20","prob_17","prob_13"]:
        d=json.load(open(find(nm))); B=d["blocks"]; bays=d["bays"]; n=len(B)
        rng=random.Random(0); mism=0; cop=0
        for _ in range(1500):
            i=rng.randrange(n); k=rng.randrange(n)
            if i==k: continue
            j=rng.randrange(len(bays)); W=bays[j]["width"]; H=bays[j]["height"]
            oi=rng.randrange(len(B[i]["shape"])); ok=rng.randrange(len(B[k]["shape"]))
            bi=M._orient_bbox(B[i],oi); bk=M._orient_bbox(B[k],ok)
            pi=CG._inbounds_pos(bi,W,H,rng); pk=CG._inbounds_pos(bk,W,H,rng)
            if not pi or not pk: continue
            xi,yi=pi; xk,yk=pk
            ei=B[i]["release_time"]; xit=ei+B[i]["processing_time"]
            ek=max(0,ei+rng.randint(-B[i]["processing_time"],B[i]["processing_time"])); xkt=ek+B[k]["processing_time"]
            if ei<xkt and ek<xit: cop+=1
            Aa,Ap=layers_arr_poly(d,i,xi,yi,oi); Ba,Bp=layers_arr_poly(d,k,xk,yk,ok)
            myc=conflict(Aa,Ap,ei,xit,Ba,Bp,ek,xkt)
            A=M.Block(block_id=i,block_data=B[i],x=xi,y=yi,orient_idx=oi); Bk=M.Block(block_id=k,block_data=B[k],x=xk,y=yk,orient_idx=ok)
            gc=CG.grader_conflict(Bay(width=W,height=H,id=j),A,Bk,ei,xit,ek,xkt)
            if myc!=gc: mism+=1
        print(f"{nm}: {cop} co-present, MISMATCHES vs grader={mism}", flush=True)
