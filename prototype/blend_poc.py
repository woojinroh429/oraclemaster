"""
Mode-BLEND POC. Same crane-feasible seating contest as contact_poc, but adds:
  - several SINGLE rules from our zoo (BL/flat, LEFT/leftbottom, DIAG/diagonal)
  - BLEND: per block, each rule proposes its best position; pick the proposal that
    leaves the largest remaining empty rectangle (keep-future-room). This mixes our
    rules WITHIN one packing (vs best-of which runs each rule as a whole packing).
Metric: seated count (more=denser) + LER + free cells. If BLEND seats more / bigger
LER than the best SINGLE rule, per-block rule mixing beats the single-mode ceiling.
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
    H,W=free.shape; heights=[0]*W; best=0
    for r in range(H):
        for c in range(W): heights[c]=heights[c]+1 if free[r,c] else 0
        st=[]; c=0; hs=heights+[0]
        while c<len(hs):
            if not st or hs[c]>=hs[st[-1]]: st.append(c); c+=1
            else:
                top=st.pop(); wdt=c if not st else c-st[-1]-1; best=max(best,hs[top]*wdt)
    return best

def paint(F, off, ix, iy, grid, W, H, val=True):
    mnx,mny=off; wx0=int(round(ix+mnx)); wy0=int(round(iy+mny))
    ys,xs=np.where(F)
    for yy,xx in zip(ys,xs):
        wx=wx0+xx; wy=wy0+yy
        if 0<=wx<W and 0<=wy<H: grid[wy,wx]=val

def single_score(rule, h, wx, wy):
    if rule=="BL":   return (h, wy, wx)
    if rule=="LEFT": return (h, wx, wy)
    if rule=="DIAG": return (wx+wy, h, wy, wx)
    return (h, wy, wx)

def best_pos_for_rule(inst, E, b, defs_b, bay, W, H, en, ex, rule):
    best=None; bestkey=None
    for oi,dd in defs_b.items():
        x0,y0=dd['off']; w,h=dd['wh']
        if w>W or h>H: continue
        for ix in range(int(np.ceil(-x0)), int(np.floor(W-1-(x0+w)))+1):
            for iy in range(int(np.ceil(-y0)), int(np.floor(H-1-(y0+h)))+1):
                if not E.placement_feasible(bay,b,oi,float(ix),float(iy),en,ex): continue
                wx=ix+x0; wy=iy+y0; key=single_score(rule,h,wx,wy)
                if bestkey is None or key<bestkey: bestkey=key; best=(oi,ix,iy,dd)
    return best

def pack(inst, blocks, bay, W, H, rule):
    B=inst["blocks"]; E=M._ogc_fast_engine(inst); E.clear_all()
    obstacle=np.zeros((H,W),bool)
    defs={b:define_block(B,b) for b in blocks}
    order=sorted(blocks, key=lambda b:-defs[b][0]['F'].sum())  # big-first
    RULES=["BL","LEFT","DIAG"]
    placed=0
    for idx,b in enumerate(order):
        en=idx; ex=len(order)+1
        if rule!="BLEND":
            best=best_pos_for_rule(inst,E,b,defs[b],bay,W,H,en,ex,rule)
        else:
            # each rule proposes; pick proposal that leaves the largest remaining LER
            props=[]
            for rl in RULES:
                p=best_pos_for_rule(inst,E,b,defs[b],bay,W,H,en,ex,rl)
                if p: props.append(p)
            best=None; bestler=-1
            seen=set()
            for (oi,ix,iy,dd) in props:
                if (oi,ix,iy) in seen: continue
                seen.add((oi,ix,iy))
                tmp=obstacle.copy(); paint(dd['F'],dd['off'],ix,iy,tmp,W,H)
                L=ler(~tmp)
                if L>bestler: bestler=L; best=(oi,ix,iy,dd)
        if best is not None:
            oi,ix,iy,dd=best
            try:
                E.add(bay,b,oi,float(ix),float(iy),en,ex)
                paint(dd['F'],dd['off'],ix,iy,obstacle,W,H); placed+=1
            except Exception: pass
    free=~obstacle
    return placed, len(order), ler(free), int(free.sum())

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json"]):
        inst=json.load(open(path)); bays=inst["bays"]
        sol=M.algorithm(inst,60); place=reconstruct(inst,sol)
        by_bay={}
        for b,p in place.items(): by_bay.setdefault(p["bay"],[]).append(b)
        bayj=max(by_bay,key=lambda j:len(by_bay[j]))
        W=bays[bayj]["width"]; H=bays[bayj]["height"]; members=by_bay[bayj]
        times=sorted({place[b]["en"] for b in members})
        def pres(t): return [b for b in members if place[b]["en"]<=t<place[b]["ex"]]
        tpk=max(times,key=lambda t:len(pres(t))); peak=pres(tpk)
        print(f"{os.path.basename(path)} bay={bayj} {W}x{H} peak={len(peak)} blocks",flush=True)
        for rule in ("BL","LEFT","DIAG","BLEND"):
            t0=time.time(); pl,tot,LER,fc=pack(inst,peak,bayj,W,H,rule); dt=time.time()-t0
            print(f"  {rule:6s}: seated {pl}/{tot} LER={LER} free={fc} ({dt:.1f}s)",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
