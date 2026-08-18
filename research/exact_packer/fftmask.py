"""FFT-correlation conflict masks -> O(1) column-pair conflict lookup.

Layer bitmaps at R=1 (unit cells, center-inside, NON-dilated so touching is allowed;
rare sliver false-negatives are caught by the solver's exact grader-verify + cut).

overlap(dx,dy) between A-layer and B-layer (B translated by unit (dx,dy)) = cross-
correlation.  For a block-pair with a fixed crane order, the conflict mask =
OR over the included (a,b) layer-index pairs of their correlations.
conflict(colA@pA, colB@pB) = mask[(pB-pA)].
"""
import os, sys, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71"))
import numpy as np
import myalgorithm as M

def _pip(verts, px, py):
    v=np.asarray(verts,float); n=len(v); inside=np.zeros(px.shape,bool)
    xs=v[:,0]; ys=v[:,1]; j=n-1
    for i in range(n):
        xi,yi=xs[i],ys[i]; xj,yj=xs[j],ys[j]
        with np.errstate(divide='ignore',invalid='ignore'):
            xint=(xj-xi)*(py-yi)/(yj-yi)+xi
        inside^=((yi>py)!=(yj>py))&(px<xint); j=i
    return inside

R=3   # subcells per unit

def raster1(verts):
    """Raster at R subcells/unit. Return (grid[ny,nx] bool, sx0, sy0) in SUBCELL index
    units: grid[0,0] center at ((sx0+0.5)/R, (sy0+0.5)/R)."""
    xs=[v[0] for v in verts]; ys=[v[1] for v in verts]
    x0,x1=math.floor(min(xs)),math.ceil(max(xs)); y0,y1=math.floor(min(ys)),math.ceil(max(ys))
    nx=(x1-x0)*R; ny=(y1-y0)*R
    if nx<=0 or ny<=0: return None,0,0
    xc=(np.arange(nx)+0.5)/R + x0; yc=(np.arange(ny)+0.5)/R + y0
    XX,YY=np.meshgrid(xc,yc)
    g=_pip(verts,XX.ravel(),YY.ravel()).reshape(ny,nx)
    return g, x0*R, y0*R    # subcell index of grid[0,0]

def block_layers1(d, bid, o):
    blk=M.Block(block_id=bid, block_data=d["blocks"][bid], x=0,y=0,orient_idx=o)
    out=[]
    for L in blk.layers_at_pos():
        if len(L)<3: out.append((None,0,0)); continue
        out.append(raster1(L))
    return out

def _xcorr(A, B):
    """C[u,v] = sum_{r,c} A[r,c]*B[r-u, c-v] for all integer (u,v). Return (C, u0, v0)
    where C[0,0] corresponds to (u,v)=(u0,v0). Via FFT."""
    ha,wa=A.shape; hb,wb=B.shape
    H=ha+hb-1; Wd=wa+wb-1
    fa=np.fft.rfft2(A.astype(float), (H,Wd))
    fb=np.fft.rfft2(B.astype(float)[::-1,::-1], (H,Wd))
    C=np.fft.irfft2(fa*fb,(H,Wd))
    # convolution of A and reversed(B): conv[i,j]=sum A[k,l] Brev[i-k,j-l]
    #   = sum A[k,l] B[hb-1-(i-k), wb-1-(j-l)]. Set u=k-(hb-1-i)=... map:
    # We want corr[u,v]=sum A[r,c] B[r-u,c-v]. Relation: conv index (i,j) with
    #   r=k, and B index (hb-1-(i-k)) = r-u -> u = i-(hb-1). similarly v=j-(wb-1).
    return C, -(hb-1), -(wb-1)   # C[0,0] is (u,v)=(u0,v0)

def overlap_mask(gA, cxA, cyA, gB, cxB, cyB):
    """Return (mask, dx0, dy0): mask[iy,ix]=True if A-layer and B-layer overlap when B
    is translated by unit offset (dx,dy)=(dx0+ix, dy0+iy)."""
    if gA is None or gB is None: return None,0,0
    C,u0,v0=_xcorr(gA,gB)   # C[u,v]>0.5 => overlap when B shifted so cells align
    ov=C>0.5
    # overlap when B translated by (dx,dy): B cell (r-u? ) ... derive dx,dy from (u,v):
    # A cell(r,c) world lower-left (cxA+c, cyA+r). B cell(rb,cb) at offset (dx,dy):
    #   (cxB+cb+dx, cyB+rb+dy). Coincide: cxA+c=cxB+cb+dx, cyA+r=cyB+rb+dy.
    #   c-cb = cxB-cxA+dx = v ; r-rb = cyB-cyA+dy = u.  => dx=v-(cxB-cxA), dy=u-(cyB-cyA)
    dx0=v0-(cxB-cxA); dy0=u0-(cyB-cyA)
    return ov, dx0, dy0

def layer_pairs(KA, KB, aEntry, aExit, bEntry, bExit):
    """(a,b) A-layer/B-layer index pairs to check, per the j>=k order-dependent rule."""
    pairs=set()
    for k in range(min(KA,KB)): pairs.add((k,k))          # resting
    if aEntry>=bEntry or aExit<=bExit:                    # A sweeps thru B (a<b): A_k vs B_{j>k}
        for k in range(KA):
            for j in range(k+1,KB): pairs.add((k,j))
    if bEntry>=aEntry or bExit<=aExit:                    # B sweeps thru A: A_{j>k} vs B_k -> (j,k), j>k
        for k in range(KB):
            for j in range(k+1,KA): pairs.add((j,k))
    return pairs

def conflict_mask(d, bidA, oA, eA, xA, bidB, oB, eB, xB):
    """Full conflict mask over unit offsets (dx,dy)=pB-pA. Return (mask, dx0, dy0)."""
    LA=block_layers1(d,bidA,oA); LB=block_layers1(d,bidB,oB)
    KA=len(LA); KB=len(LB)
    prs=layer_pairs(KA,KB,eA,xA,eB,xB)
    acc=None; DX0=DY0=None; shape=None
    subs=[]
    for (a,b) in prs:
        gA,cxA,cyA=LA[a]; gB,cxB,cyB=LB[b]
        ov,dx0,dy0=overlap_mask(gA,cxA,cyA,gB,cxB,cyB)
        if ov is None: continue
        subs.append((ov,dx0,dy0))
    if not subs: return None,0,0
    # union onto a common offset grid
    dxmin=min(s[1] for s in subs); dymin=min(s[2] for s in subs)
    dxmax=max(s[1]+s[0].shape[1]-1 for s in subs); dymax=max(s[2]+s[0].shape[0]-1 for s in subs)
    Wd=dxmax-dxmin+1; Hd=dymax-dymin+1
    mask=np.zeros((Hd,Wd),bool)
    for ov,dx0,dy0 in subs:
        mask[dy0-dymin:dy0-dymin+ov.shape[0], dx0-dxmin:dx0-dxmin+ov.shape[1]]|=ov
    return mask, dxmin, dymin

def lookup(mask, dx0, dy0, dx, dy):
    """dx,dy = UNIT offset (pB-pA). Mask origin dx0,dy0 in SUBCELL units."""
    if mask is None: return False
    ix=R*dx-dx0; iy=R*dy-dy0
    if iy<0 or ix<0 or iy>=mask.shape[0] or ix>=mask.shape[1]: return False
    return bool(mask[iy,ix])

if __name__=="__main__":
    # verify mask lookup vs fastconf.conflict (exact) on random column pairs
    import json, random
    sys.path.insert(0, os.path.join(SP,"research"))
    import fastconf as FC
    def find(n):
        for sub in ("data/training_instances/train","data/train"):
            p=os.path.join(SP,sub,n+".json")
            if os.path.exists(p): return p
    for nm in ["prob_20","prob_17"]:
        d=json.load(open(find(nm))); B=d["blocks"]; bays=d["bays"]
        rng=random.Random(2); mism=0; fn=0; N=0
        for _ in range(400):
            i=rng.randrange(len(B)); k=rng.randrange(len(B))
            if i==k: continue
            oi=rng.randrange(len(B[i]["shape"])); ok=rng.randrange(len(B[k]["shape"]))
            ei=B[i]["release_time"]; xit=ei+B[i]["processing_time"]
            ek=max(0,ei+rng.randint(-8,8)); xkt=ek+B[k]["processing_time"]
            if not(ei<xkt and ek<xit): continue
            mask,dx0,dy0=conflict_mask(d,i,oi,ei,xit,k,ok,ek,xkt)
            for _t in range(4):
                xi=rng.randint(0,20); yi=rng.randint(0,20); xk=rng.randint(0,20); yk=rng.randint(0,20)
                dx=xk-xi; dy=yk-yi
                mc=lookup(mask,dx0,dy0,dx,dy)
                Aa,Ap=FC.layers_arr_poly(d,i,xi,yi,oi); Ba,Bp=FC.layers_arr_poly(d,k,xk,yk,ok)
                ex=FC.conflict(Aa,Ap,ei,xit,Ba,Bp,ek,xkt)
                N+=1
                if mc!=ex:
                    mism+=1
                    if mc==False and ex==True: fn+=1
        print(f"{nm}: {N} tests, MISMATCH={mism} (false-neg={fn})", flush=True)
