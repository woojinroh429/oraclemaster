"""COMPUTE-CONCENTRATION test: can v77's OWN engine, given the full budget on a
single binding bay (as a 1-bay sub-instance), beat the per-bay Z1 it achieved
under the shared 3-bay budget?  If yes, that is a DIRECT improvement to v77 (no
master/Benders needed): just replace that bay's schedule.
Usage: python3.12 subbay.py prob_38 [TL=60] [bays=1,2]
"""
import json, os, sys, copy, time
from collections import defaultdict
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import myalgorithm as M
from utils import check_feasibility

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
TL=float(sys.argv[2]) if len(sys.argv)>2 else 60.0
TARGET=[int(x) for x in sys.argv[3].split(",")] if len(sys.argv)>3 else None
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
d=json.load(open(find(NAME))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays)
due=[B[b]["due_date"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]

# v77 baseline + per-bay assignment & in-context bay-Z1
best=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY": pl[op["block_id"]]=dict(bay=op["bay_id"],ex=int(tk)+pt[op["block_id"]])
        best=(ck["objective"],ck["obj1"],pl)
objv,z1v,place=best
bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)
print(f"{NAME}: v77 obj={objv:.0f} Z1={z1v:.0f}   (compute-concentration, per-bay TL={TL})",flush=True)
tgt = TARGET if TARGET is not None else list(range(m))

def sub_instance(j):
    bl=sorted(bybay[j])
    sd={"name":f"{NAME}_bay{j}","bays":[copy.deepcopy(bays[j])],"weights":copy.deepcopy(d["weights"]),"blocks":[]}
    for b in bl:
        nb=copy.deepcopy(B[b]); nb["bay_preferences"]=[B[b]["bay_preferences"][j]]; sd["blocks"].append(nb)
    return sd, bl

for j in tgt:
    bl=bybay[j]
    if not bl: continue
    v77z1=sum(max(0,place[b]["ex"]-due[b]) for b in bl)
    sd,order=sub_instance(j)
    t0=time.time()
    bestsub=None
    for _ in range(2):
        s2=M.algorithm(sd, TL/2); c2=check_feasibility(sd,s2)
        if c2["feasible"] and (bestsub is None or c2["obj1"]<bestsub): bestsub=c2["obj1"]
    dt=time.time()-t0
    win = f"WIN -{round(100*(v77z1-bestsub)/max(1,v77z1))}%" if bestsub is not None and bestsub<v77z1 else (f"+{bestsub-v77z1}" if bestsub is not None else "INFEAS")
    print(f"  bay{j}: {len(bl)} blk  standalone-v77 bay-Z1={bestsub}  (in-context {v77z1})  {win}  [{dt:.0f}s]",flush=True)
