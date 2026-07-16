# Overhang vs fragmentation: for the waiting block, count FOOTPRINT-feasible positions
# (2D no-overlap, ignoring crane descent) vs CRANE-feasible. If footprint>0 but crane=0
# -> overhangs block real 2D gaps -> corridor-first lever. If footprint=0 -> the block is
# too big for any gap (fragmentation) -> corridor won't help; needs denser packing.
import os,sys,json
os.environ.setdefault("ENGINE_DIR",".") ; sys.path.insert(0,".")
import numpy as np, myalgorithm as M
from corridor_diag2 import reconstruct, bbox, raster_union
for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json"]):
    inst=json.load(open(path));B=inst["blocks"];bays=inst["bays"]
    sol=M.algorithm(inst,60);place=reconstruct(inst,sol);nm=os.path.basename(path)[:-5]
    cand=[(b,p) for b,p in place.items() if max(0,p["ex"]-B[b]["due_date"])>0 and p["en"]>B[b]["release_time"]]
    hb,ha=max(cand,key=lambda r:r[1]["ex"]-B[r[0]]["due_date"]);bayj=ha["bay"]
    W=bays[bayj]["width"];H=bays[bayj]["height"];rel=B[hb]["release_time"];enter=ha["en"];oi=ha["oi"]
    # block hb footprint mask (normalized)
    x0,y0,x1,y1=bbox(B,hb,oi)
    hbmask=raster_union(B[hb]["shape"][oi]["layers"], -x0,-y0, int(np.ceil(x1-x0))+1,int(np.ceil(y1-y0))+1)
    hh,hw=hbmask.shape
    fp_tot=0;cr_tot=0
    for t in range(rel,enter):
        pres=[b for b,p in place.items() if b!=hb and p["bay"]==bayj and p["en"]<=t<p["ex"]]
        occ=np.zeros((H,W),bool)
        for b in pres:
            a=place[b];occ|=raster_union(B[b]["shape"][a["oi"]]["layers"],a["x"],a["y"],W,H)
        E=M._ogc_fast_engine(inst);E.clear_all()
        for b in pres:
            a=place[b]
            try:E.add(bayj,b,int(a["oi"]),float(a["x"]),float(a["y"]),int(a["en"]),int(a["ex"]))
            except:pass
        ex=t+B[hb]["processing_time"];fp=0;cr=0
        for ix in range(int(np.ceil(-x0)),int(np.floor(W-x1))+1):
            for iy in range(int(np.ceil(-y0)),int(np.floor(H-y1))+1):
                # footprint-feasible: hbmask placed at (ix+x0,iy+y0) fits in free floor
                wx=int(round(ix+x0));wy=int(round(iy+y0))
                if wx<0 or wy<0 or wx+hw>W or wy+hh>H: continue
                sub=occ[wy:wy+hh,wx:wx+hw]
                if not np.any(sub&hbmask): fp+=1
                if E.placement_feasible(bayj,hb,int(oi),float(ix),float(iy),t,ex): cr+=1
        fp_tot+=fp;cr_tot+=cr
    verdict = "OVERHANG (corridor-first lever!)" if fp_tot>0 and cr_tot==0 else ("FRAGMENTATION (needs denser packing, not corridor)" if fp_tot==0 else "mixed")
    print(f"{nm}: block {hb} across wait-times | FOOTPRINT-feasible positions={fp_tot} | CRANE-feasible={cr_tot} => {verdict}",flush=True)
print("ALLDONE")
