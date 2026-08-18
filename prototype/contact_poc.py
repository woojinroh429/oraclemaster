"""
Contact-max (density) vs bottom-left packing contest on a real congested bay.
Same block set, same bay, same arrival order, crane-feasible (C++ engine). Two
position-selection rules:
  BL      : score (h, wy, wx)  -> flat/bottom-left (our flatbl proxy)
  CONTACT : maximize contact = shell cells touching obstacle footprint or wall
            (the FFT density score, computed directly here; FFT is the fast impl)
Metric: how many blocks seat (more = denser), + largest-empty-rectangle & free cells
after packing. If CONTACT seats more / leaves a bigger contiguous region, the density
hypothesis (and thus the friend's FFT edge) has legs.
"""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import numpy as np
import myalgorithm as M
from block_def import define_block

def reconstruct(inst, sol):
    ops=sol["operations"]; place={}
    for ts,lst in ops.items():
        t=int(ts)
        for o in lst:
            b=o["block_id"]
            if o["type"]=="ENTRY":
                place.setdefault(b,{}).update(bay=o["bay_id"],x=o["x"],y=o["y"],oi=o["orient_idx"],en=t)
            else: place.setdefault(b,{})["ex"]=t
    for b,p in place.items():
        if "ex" not in p: p["ex"]=p["en"]+inst["blocks"][b]["processing_time"]
    return place

def ler(free):
    """largest all-True axis-aligned rectangle area in bool grid `free` (H,W)."""
    H,W=free.shape; heights=[0]*W; best=0
    for r in range(H):
        for c in range(W):
            heights[c]=heights[c]+1 if free[r,c] else 0
        # largest rectangle in histogram
        st=[]; c=0
        hs=heights+[0]
        while c<len(hs):
            if not st or hs[c]>=hs[st[-1]]:
                st.append(c); c+=1
            else:
                top=st.pop(); wdt=c if not st else c-st[-1]-1
                best=max(best, hs[top]*wdt)
        st=[]
    return best

def contact_score(D, off, ix, iy, obstacle, W, H):
    """count shell cells hitting obstacle or lying on/over the wall."""
    mnx,mny=off
    wx0=int(round(ix+mnx)); wy0=int(round(iy+mny))
    dh,dw=D.shape
    hit=0; wall=0
    ys,xs=np.where(D)
    for yy,xx in zip(ys,xs):
        wx=wx0+xx; wy=wy0+yy
        if wx<0 or wx>=W or wy<0 or wy>=H: wall+=1
        elif obstacle[wy,wx]: hit+=1
    return hit+wall

def paint(F, off, ix, iy, grid, W, H):
    mnx,mny=off; wx0=int(round(ix+mnx)); wy0=int(round(iy+mny))
    ys,xs=np.where(F)
    for yy,xx in zip(ys,xs):
        wx=wx0+xx; wy=wy0+yy
        if 0<=wx<W and 0<=wy<H: grid[wy,wx]=True

def pack(inst, blocks, bay, W, H, rule):
    B=inst["blocks"]
    E=M._ogc_fast_engine(inst); E.clear_all()
    obstacle=np.zeros((H,W),bool)
    defs={b:define_block(B,b) for b in blocks}
    placed=0; order=sorted(blocks, key=lambda b:-defs[b][0]['F'].sum())  # big-first
    for idx,b in enumerate(order):
        en=idx; ex=len(order)+1   # all co-present; arrival order = descent order
        best=None; bestkey=None
        for oi,dd in defs[b].items():
            x0,y0=dd['off']; w,h=dd['wh']
            if w>W or h>H: continue
            for ix in range(int(np.ceil(-x0)), int(np.floor(W-1-(x0+w)))+1):
                for iy in range(int(np.ceil(-y0)), int(np.floor(H-1-(y0+h)))+1):
                    if not E.placement_feasible(bay,b,oi,float(ix),float(iy),en,ex): continue
                    wx=ix+x0; wy=iy+y0
                    if rule=="BL":
                        key=(h, wy, wx)         # minimize
                    else:
                        c=contact_score(dd['D'],dd['off'],ix,iy,obstacle,W,H)
                        key=(-c, h, wy, wx)     # maximize contact, then flat/bl
                    if bestkey is None or key<bestkey:
                        bestkey=key; best=(oi,ix,iy,dd)
        if best is not None:
            oi,ix,iy,dd=best
            try:
                E.add(bay,b,oi,float(ix),float(iy),en,ex)
                paint(dd['F'],dd['off'],ix,iy,obstacle,W,H); placed+=1
            except Exception: pass
    free=~obstacle
    return placed, len(order), ler(free), int(free.sum())

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "../data/train/prob_28.json"
    inst=json.load(open(path)); bays=inst["bays"]
    sol=M.algorithm(inst,60); place=reconstruct(inst,sol)
    # busiest bay + its peak co-present set
    by_bay={}
    for b,p in place.items(): by_bay.setdefault(p["bay"],[]).append(b)
    bayj=max(by_bay,key=lambda j:len(by_bay[j]))
    W=bays[bayj]["width"]; H=bays[bayj]["height"]; members=by_bay[bayj]
    times=sorted({place[b]["en"] for b in members})
    def pres(t): return [b for b in members if place[b]["en"]<=t<place[b]["ex"]]
    tpk=max(times,key=lambda t:len(pres(t))); peak=pres(tpk)
    print(f"{os.path.basename(path)} bay={bayj} {W}x{H} peak-time={tpk} co-present={len(peak)} blocks",flush=True)
    for rule in ("BL","CONTACT"):
        t0=time.time(); pl,tot,LER,freec=pack(inst,peak,bayj,W,H,rule); dt=time.time()-t0
        print(f"  {rule:8s}: seated {pl}/{tot} | LER={LER} free_cells={freec} ({dt:.1f}s)",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
