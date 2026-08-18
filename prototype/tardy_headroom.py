"""
Tardiness-headroom diagnostic. For a solved instance:
  - which blocks are tardy (exit_time > due_date)?
  - did they WAIT after release (entry_time > release_time)?  waiting -> avoidable-ish
  - at the block's release time, was there a LESS-congested bay it could have used?
This tells us whether Z1 (tardiness) has scheduling headroom or is a hard floor.
"""
import os, sys, json
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M

def reconstruct(sol):
    ops=sol["operations"]; place={}
    for ts,lst in ops.items():
        t=int(ts)
        for o in lst:
            b=o["block_id"]
            if o["type"]=="ENTRY":
                place.setdefault(b,{}).update(bay=o["bay_id"],x=o["x"],y=o["y"],oi=o["orient_idx"],en=t)
            else: place.setdefault(b,{})["ex"]=t
    return place

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json"]):
        inst=json.load(open(path)); B=inst["blocks"]; nbay=len(inst["bays"])
        sol=M.algorithm(inst,60); place=reconstruct(sol)
        nm=os.path.basename(path).replace(".json","")
        # per-bay timeline of occupancy (count present)
        maxt=max(p["ex"] for p in place.values() if "ex" in p)
        occ=[[0]*(maxt+2) for _ in range(nbay)]
        for b,p in place.items():
            if "en" in p and "ex" in p:
                for t in range(p["en"],p["ex"]): occ[p["bay"]][t]+=1
        tardy=[]; waited_tardy=0; wait_sum=0; alt_bay_free=0
        for b,p in place.items():
            if "en" not in p or "ex" not in p: continue
            due=B[b]["due_date"]; rel=B[b]["release_time"]
            tard=max(0,p["ex"]-due)
            if tard>0:
                tardy.append((b,tard))
                wait=p["en"]-rel
                if wait>0:
                    waited_tardy+=1; wait_sum+=wait
                    # at release, was another bay less busy than the chosen one?
                    relt=min(rel,maxt)
                    mine=occ[p["bay"]][relt]
                    others=[occ[j][relt] for j in range(nbay) if j!=p["bay"]]
                    if others and min(others)<mine: alt_bay_free+=1
        totz1=sum(t for _,t in tardy)
        prefs_ok=sum(1 for b,p in place.items() if "en" in p and
                     B[b]["bay_preferences"][p["bay"]]==max(B[b]["bay_preferences"]))
        print(f"{nm}: nbay={nbay} Z1={totz1} tardy_blocks={len(tardy)} | "
              f"waited-after-release={waited_tardy} (Σwait={wait_sum}) | "
              f"of those, alt-bay-less-busy-at-release={alt_bay_free} | "
              f"blocks-in-preferred-bay={prefs_ok}/{len(place)}")
    print("ALLDONE")

if __name__=="__main__": main()
