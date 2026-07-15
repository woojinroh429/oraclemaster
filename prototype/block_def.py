"""
Concrete block definition for the FFT density/contact POC.
For each orientation: footprint mask F (union of layer polygons, rasterized at
unit grid), dilated shell D (F grown 1 cell), and the local-origin offset.
Feasibility is NOT done here (stays exact via the C++ engine); this is scoring-only.
Demonstrates on real prob_28 blocks and prints ASCII so we can eyeball correctness.
"""
import os, sys, json
sys.path.insert(0, ".")
import numpy as np

def rasterize_union(layers, ox, oy, W, H):
    """Union of all layer polygons -> footprint bool mask (H,W), shifted by (ox,oy)."""
    full = np.zeros((H, W), bool)
    for verts in layers:
        v = np.asarray(verts, float) + np.array([ox, oy])
        if len(v) < 3: continue
        x0=max(0,int(np.floor(v[:,0].min()))); x1=min(W,int(np.ceil(v[:,0].max())))
        y0=max(0,int(np.floor(v[:,1].min()))); y1=min(H,int(np.ceil(v[:,1].max())))
        if x1<=x0 or y1<=y0: continue
        xs=np.arange(x0,x1)+0.5; ys=np.arange(y0,y1)+0.5; gx,gy=np.meshgrid(xs,ys)
        inside=np.zeros(gx.shape,bool); n=len(v); j=n-1
        for i in range(n):
            xi,yi=v[i]; xj,yj=v[j]
            inside ^= ((yi>gy)!=(yj>gy)) & (gx < (xj-xi)*(gy-yi)/(yj-yi+1e-12)+xi); j=i
        full[y0:y1,x0:x1] |= inside
    return full

def dilate1(m):
    d = m.copy()
    d[1:,:]|=m[:-1,:]; d[:-1,:]|=m[1:,:]; d[:,1:]|=m[:,:-1]; d[:,:-1]|=m[:,1:]
    return d

def define_block(B, b):
    """Return {oi: {'F':mask,'D':shell,'off':(ox,oy),'wh':(w,h)}} at local origin."""
    out={}
    for oi, orient in enumerate(B[b]["shape"]):
        layers=orient["layers"]
        allv=np.array([q for l in layers for q in l], float)
        mnx,mny=allv[:,0].min(), allv[:,1].min()
        mxx,mxy=allv[:,0].max(), allv[:,1].max()
        w=int(np.ceil(mxx-mnx)); h=int(np.ceil(mxy-mny))
        F=rasterize_union(layers, -mnx, -mny, w+1, h+1)
        D=dilate1(F) & ~F                     # contact shell = boundary ring only
        out[oi]={'F':F,'D':D,'off':(mnx,mny),'wh':(w,h)}
    return out

def ascii_mask(m, ch='#'):
    return "\n".join("".join(ch if v else '.' for v in row) for row in m[::-1])  # y-up

def main():
    inst=json.load(open("../data/train/prob_28.json")); B=inst["blocks"]
    for b in (0, 82):
        d=define_block(B, b)
        oi=0; F=d[oi]['F']; D=d[oi]['D']
        print(f"=== block {b} orient 0: footprint {d[oi]['wh']} cells, "
              f"|F|={int(F.sum())} solid, |D|={int(D.sum())} shell, off={tuple(round(x,2) for x in d[oi]['off'])}, "
              f"n_orients={len(d)} ===")
        print("footprint F:")
        print(ascii_mask(F))
        print("contact shell D (1-cell ring):")
        print(ascii_mask(D, '+'))
        print()
    print("ALLDONE")

if __name__=="__main__": main()
