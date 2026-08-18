"""
Load diagnosis: is P4 tardiness an IMBALANCE problem (one bay overloaded, others
idle -> fixable by rebalancing) or a SATURATION problem (all bays full in the
congested window -> capacity floor)? Per bay per time: #present + area-utilization.
Focus on times where tardy blocks are waiting.
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

def amin(B,b,oi):
    L=B[b]["shape"][oi]["layers"]; xs=[q[0] for l in L for q in l]; ys=[q[1] for l in L for q in l]
    return (max(xs)-min(xs))*(max(ys)-min(ys))

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json"]):
        inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]; m=len(bays)
        cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
        sol=M.algorithm(inst,60); place=reconstruct(inst,sol)
        nm=os.path.basename(path).replace(".json","")
        maxt=max(p["ex"] for p in place.values())
        # times where a released-but-not-yet-entered tardy block is WAITING
        wait_times=set()
        for b,p in place.items():
            rel=B[b]["release_time"]; tardy=max(0,p["ex"]-B[b]["due_date"])>0
            if tardy and p["en"]>rel:
                for t in range(rel,p["en"]): wait_times.add(t)
        # per-bay util at those wait times: min/mean/max over bays
        rows=[]
        for t in sorted(wait_times):
            util=[]
            for j in range(m):
                a=sum(amin(B,b,place[b]["oi"]) for b,p in place.items()
                      if p["bay"]==j and p["en"]<=t<p["ex"])
                util.append(a/cap[j])
            rows.append((t,util))
        if not rows:
            print(f"{nm}: no waiting"); continue
        # aggregate: at a typical wait time, what's the MIN-bay util (the emptiest bay)?
        min_utils=[min(u) for _,u in rows]      # emptiest bay's util at each wait time
        max_utils=[max(u) for _,u in rows]
        spreads=[max(u)-min(u) for _,u in rows]
        print(f"{nm} m={m} caps={cap}: wait-times={len(rows)} | "
              f"emptiest-bay util avg={np.mean(min_utils):.0%} (if LOW -> rebalance possible) | "
              f"fullest-bay util avg={np.mean(max_utils):.0%} | "
              f"imbalance(max-min) avg={np.mean(spreads):.0%}",flush=True)
        # show a couple of the worst wait moments
        worst=sorted(rows,key=lambda r:-min(r[1]))[:3]
        for t,u in worst:
            print(f"    t={t}: per-bay util = {[f'{x:.0%}' for x in u]}",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
