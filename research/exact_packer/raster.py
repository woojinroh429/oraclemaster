"""Rasterize layer polygons to bitmaps and compute conflict masks over relative
offsets via 2D correlation.  Enables O(1) column-pair conflict lookup.

Resolution R: cells per unit. Occupancy = polygon covers cell CENTER. Two layers
overlap at INTEGER offset (dx,dy) iff their occupied cells overlap when B is shifted.
Verified against the numba/shapely exact conflict; the search uses this + an exact
grader-verify on the final solution to stay correct."""
import os, sys, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71"))
import numpy as np
import myalgorithm as M

R=2  # subcells per unit

def _pip(verts, px, py):
    """vectorized even-odd point-in-polygon; px,py 1-D arrays -> bool array."""
    v=np.asarray(verts,dtype=float); n=len(v)
    inside=np.zeros(px.shape, dtype=bool)
    xs=v[:,0]; ys=v[:,1]
    j=n-1
    for i in range(n):
        xi,yi=xs[i],ys[i]; xj,yj=xs[j],ys[j]
        cond=((yi>py)!=(yj>py))
        # avoid div by zero
        with np.errstate(divide='ignore',invalid='ignore'):
            xint=(xj-xi)*(py-yi)/(yj-yi)+xi
        inside ^= cond & (px < xint)
        j=i
    return inside

def raster_layer(verts):
    """verts (world coords at placement (0,0)). Return (grid bool [ny,nx], sx, sy):
    grid[iy,ix] occupied; grid[0,0] is subcell index (sx, sy) (integer, in 1/R units).
    Conservatively dilated by 1 subcell -> no sliver-overlap false-negatives."""
    xs=[v[0] for v in verts]; ys=[v[1] for v in verts]
    x0,x1=math.floor(min(xs)),math.ceil(max(xs)); y0,y1=math.floor(min(ys)),math.ceil(max(ys))
    nx=(x1-x0)*R; ny=(y1-y0)*R
    if nx<=0 or ny<=0: return None,0,0
    xc=(np.arange(nx)+0.5)/R + x0
    yc=(np.arange(ny)+0.5)/R + y0
    XX,YY=np.meshgrid(xc,yc)
    inside=_pip(verts, XX.ravel(), YY.ravel()).reshape(ny,nx)
    g=np.zeros((ny+2,nx+2),bool); g[1:-1,1:-1]=inside
    dg=g.copy(); dg[1:,:]|=g[:-1,:]; dg[:-1,:]|=g[1:,:]; dg[:,1:]|=g[:,:-1]; dg[:,:-1]|=g[:,1:]
    return dg, x0*R - 1, y0*R - 1     # grid[0,0] subcell index (padded by 1)

def layer_bitmaps(d, bid, o):
    blk=M.Block(block_id=bid, block_data=d["blocks"][bid], x=0, y=0, orient_idx=o)
    out=[]
    for L in blk.layers_at_pos():
        if len(L)<3: out.append((None,0,0)); continue
        out.append(raster_layer(L))
    return out

def grids_overlap(gA, sxA, syA, gB, sxB, syB, dx, dy):
    """A at origin; B shifted by integer (dx,dy) units. Overlap in subcell index space."""
    if gA is None or gB is None: return False
    Ax0=sxA; Ay0=syA; Bx0=sxB+dx*R; By0=syB+dy*R
    ax1=Ax0+gA.shape[1]; ay1=Ay0+gA.shape[0]; bx1=Bx0+gB.shape[1]; by1=By0+gB.shape[0]
    ix0=max(Ax0,Bx0); ix1=min(ax1,bx1); iy0=max(Ay0,By0); iy1=min(ay1,by1)
    if ix0>=ix1 or iy0>=iy1: return False
    return bool(np.any(gA[iy0-Ay0:iy1-Ay0, ix0-Ax0:ix1-Ax0] &
                       gB[iy0-By0:iy1-By0, ix0-Bx0:ix1-Bx0]))

if __name__=="__main__":
    # verify grids_overlap vs numba _cl over random offsets
    import json, random
    sys.path.insert(0, os.path.join(SP,"research"))
    import fastconf as FC
    def find(n):
        for sub in ("data/training_instances/train","data/train"):
            p=os.path.join(SP,sub,n+".json")
            if os.path.exists(p): return p
    d=json.load(open(find("prob_20"))); B=d["blocks"]
    rng=random.Random(1); mism=0; N=0; fn=0
    for _ in range(3000):
        i=rng.randrange(len(B)); k=rng.randrange(len(B))
        oi=rng.randrange(len(B[i]["shape"])); ok=rng.randrange(len(B[k]["shape"]))
        bmA=layer_bitmaps(d,i,oi); bmB=layer_bitmaps(d,k,ok)
        dx=rng.randint(-15,15); dy=rng.randint(-15,15)
        for a in range(len(bmA)):
            for b in range(len(bmB)):
                gA,oxA,oyA=bmA[a]; gB,oxB,oyB=bmB[b]
                bit=grids_overlap(gA,oxA,oyA,gB,oxB,oyB,dx,dy)
                # exact: A layer a at (0,0), B layer b at (dx,dy)
                Aa,Ap=FC.layers_arr_poly(d,i,0,0,oi); Ba,Bp=FC.layers_arr_poly(d,k,dx,dy,ok)
                ex=FC._cl(Aa[a],Ba[b],Ap[a],Bp[b])
                N+=1
                if bit!=ex:
                    mism+=1
                    if bit==False and ex==True: fn+=1
        if _>200 and N>4000: break
    print(f"raster R={R}: {N} layer-pair tests, MISMATCH={mism} (false-neg={fn})", flush=True)
