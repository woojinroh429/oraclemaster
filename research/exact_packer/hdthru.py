"""High-density THROUGHPUT headroom probe. Does v71 under-pack congested bays (leave
crane-feasible concurrency on the table)? At the peak-congestion instant of each bay,
compare v71's actual concurrent-present count vs cranepack's max crane-feasible concurrent
set (of the SAME assigned blocks, entry=their v71 entry allowed to shift earlier)."""
import json, os, sys, time
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"cc"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
from utils import check_feasibility
import cranepack as CP
from collections import defaultdict

def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_26"
TL=float(sys.argv[2]) if len(sys.argv)>2 else 25
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 6
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]
sol=M.algorithm(inst,TL); ck=check_feasibility(inst,sol)
place={}
for tk,lst in sol["operations"].items():
    for op in lst:
        if op.get("type")=="ENTRY":
            place[op["block_id"]]=dict(bay=op["bay_id"],x=op["x"],y=op["y"],oi=op["orient_idx"],en=int(tk),ex=int(tk)+pt[op["block_id"]])
print(f"{NAME}: obj={ck['objective']:.0f} Z1={ck['obj1']:.0f}  [{TL}s]")

def OL(bid,o):
    return [np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=bid,block_data=B[bid],x=0,y=0,orient_idx=o).layers_at_pos()]
def obb(b,o): return M._orient_bbox(B[b],o)

for bay in range(m):
    inbay=[b for b in place if place[b]["bay"]==bay]
    if len(inbay)<4: continue
    # peak instant = time with most concurrent present
    times=sorted(set(place[b]["en"] for b in inbay))
    def present(t): return [b for b in inbay if place[b]["en"]<=t<place[b]["ex"]]
    peak_t=max(times,key=lambda t:len(present(t)))
    P=present(peak_t); actual=len(P)
    # cranepack max concurrent: which of the present-or-waiting blocks (released by peak_t)
    # can be crane-feasible simultaneously at ONE instant (entry fixed = peak_t)?
    cand=[b for b in inbay if rel[b]<=peak_t]  # could be present
    W=bays[bay]["width"]; H=bays[bay]["height"]; bin=[]
    for bid in cand:
        bin.append(([OL(bid,o) for o in range(len(B[bid]["shape"]))],
                    [tuple(float(v) for v in obb(bid,o)) for o in range(len(B[bid]["shape"]))],
                    [(0,1)]))   # all co-present at one instant
    t0=time.time(); res=CP.pack(bin,float(W),float(H),STEP,2.0,seed=1,warm=None); dt=time.time()-t0
    maxc=res[0]
    flag="  <== UNDER-PACK" if maxc>actual else ""
    print(f"  bay{bay}@t{peak_t}: v71 concurrent={actual}  cranepack max-concurrent={maxc}/{len(cand)} released  [{dt:.1f}s]{flag}")
