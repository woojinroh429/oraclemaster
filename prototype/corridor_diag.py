"""
Premise check for corridor-first construction: at congested times, how much FREE
floor is crane-INACCESSIBLE (a probe block can't descend there because of overhangs)
vs crane-accessible? If a large fraction is inaccessible -> descent-shadow is real ->
corridor-first (protect descent corridors) has a target. If ~all free floor is
accessible -> the limit is footprint packing, not corridors.
"""
import os, sys, json
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import numpy as np
import myalgorithm as M

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

def bbox(B,b,oi):
    L=B[b]["shape"][oi]["layers"]; xs=[q[0] for l in L for q in l]; ys=[q[1] for l in L for q in l]
    return min(xs),min(ys),max(xs),max(ys)

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json"]):
        inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]
        sol=M.algorithm(inst,60); place=reconstruct(inst,sol)
        nm=os.path.basename(path).replace(".json","")
        by_bay={}
        for b,p in place.items(): by_bay.setdefault(p["bay"],[]).append(b)
        bayj=max(by_bay,key=lambda j:len(by_bay[j])); mem=by_bay[bayj]
        W=bays[bayj]["width"]; H=bays[bayj]["height"]
        def present(t): return [b for b in mem if place[b]["en"]<=t<place[b]["ex"]]
        times=sorted({place[b]["en"] for b in mem})
        tpk=max(times,key=lambda t:len(present(t)))
        pres=present(tpk)
        # build engine with present blocks at tpk
        E=M._ogc_fast_engine(inst); E.clear_all()
        for b in pres:
            a=place[b]
            try: E.add(bayj,b,int(a["oi"]),float(a["x"]),float(a["y"]),int(a["en"]),int(a["ex"]))
            except Exception: pass
        # occupied floor cells (footprint union of present blocks) via engine feasibility probe
        # pick a small probe block from the instance (smallest footprint, 1 layer if any)
        probe=min(range(len(B)), key=lambda b:(bbox(B,b,0)[2]-bbox(B,b,0)[0])*(bbox(B,b,0)[3]-bbox(B,b,0)[1]))
        x0,y0,x1,y1=bbox(B,probe,0); pw=x1-x0; ph=y1-y0
        en=tpk; ex=tpk+1
        total_pos=0; accessible=0
        for ix in range(int(np.ceil(-x0)),int(np.floor(W-x1))+1):
            for iy in range(int(np.ceil(-y0)),int(np.floor(H-y1))+1):
                total_pos+=1
                if E.placement_feasible(bayj,probe,0,float(ix),float(iy),en,ex): accessible+=1
        # also: a MEDIAN-size probe
        areas=sorted(range(len(B)),key=lambda b:(bbox(B,b,0)[2]-bbox(B,b,0)[0])*(bbox(B,b,0)[3]-bbox(B,b,0)[1]))
        mprobe=areas[len(areas)//2]
        mx0,my0,mx1,my1=bbox(B,mprobe,0)
        mtot=0; macc=0
        if (mx1-mx0)<=W and (my1-my0)<=H:
            for ix in range(int(np.ceil(-mx0)),int(np.floor(W-mx1))+1):
                for iy in range(int(np.ceil(-my0)),int(np.floor(H-my1))+1):
                    mtot+=1
                    if E.placement_feasible(bayj,mprobe,0,float(ix),float(iy),en,ex): macc+=1
        print(f"{nm} bay={bayj} {W}x{H} peak={len(pres)}blk | "
              f"SMALL probe({pw:.0f}x{ph:.0f}): {accessible}/{total_pos} crane-accessible ({100*accessible//max(1,total_pos)}%) | "
              f"MED probe: {macc}/{mtot} accessible ({100*macc//max(1,mtot)}%)",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
