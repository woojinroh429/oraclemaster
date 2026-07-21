"""Decisive cheap measurement: at prob_38's binding (most-congested) instant per
bay, can cranepack co-place MORE blocks/area than v77 achieved there?
  - If yes  -> v77 leaves concurrency on the table -> crane-capacity master has room.
  - If no   -> v77 is already crane-optimal -> the whole schedule-first idea is dead.
Usage: python3.12 capprobe.py prob_38
"""
import json, os, sys, time
import numpy as np
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP
from collections import defaultdict

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]

# best-of-2 v77 baseline placement
best=None
for _ in range(2):
    sol=M.algorithm(inst,30); ck=check_feasibility(inst,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY":
                    b=op["block_id"]; pl[b]=dict(bay=op["bay_id"],x=op["x"],y=op["y"],oi=op["orient_idx"],en=int(tk),ex=int(tk)+pt[b])
        best=(ck["objective"],ck["obj1"],pl)
_,z1,place=best
print(f"{NAME}: v77 Z1={z1:.0f}",flush=True)

_olc={}
def OL(bid,o):
    k=(bid,o)
    if k not in _olc: _olc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=bid,block_data=B[bid],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[k]
def obb(b,o): return M._orient_bbox(B[b],o)
def foot(b,o):  # footprint bbox area proxy
    x0,y0,x1,y1=obb(b,o); return (x1-x0)*(y1-y0)

bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)

for j in range(m):
    bl=bybay[j]
    if not bl: continue
    W=bays[j]["width"]; H=bays[j]["height"]
    # find v77's most-congested instant in this bay
    ev=sorted(set([place[b]["en"] for b in bl]))
    def conc(t): return [b for b in bl if place[b]["en"]<=t<place[b]["ex"]]
    tstar=max(ev, key=lambda t:len(conc(t)))
    v77set=conc(tstar); v77cnt=len(v77set)
    # candidate pool: ALL blocks (this bay) that COULD be present at tstar (released, not past due window)
    pool=[b for b in bl if rel[b]<=tstar]      # released by tstar
    # cap pool for tractable cranepack
    pool=sorted(pool, key=lambda b:due[b])[:40]
    binL=[]; cli=[]
    for b in pool:
        cli.append(b)
        binL.append(([OL(b,o) for o in range(len(B[b]["shape"]))],
                     [tuple(float(v) for v in obb(b,o)) for o in range(len(B[b]["shape"]))],
                     [(int(tstar),int(tstar+pt[b]))]))
    t0=time.time()
    res=CP.pack(binL,float(W),float(H),4,1.5,seed=1,warm=None,frozen=None)
    cp_cnt=len(res[1])
    print(f"  bay{j} @t={tstar}: v77_concurrent={v77cnt}  cranepack_max={cp_cnt} (pool={len(pool)})  "
          f"{'ROOM +'+str(cp_cnt-v77cnt) if cp_cnt>v77cnt else 'no room'}  [{time.time()-t0:.1f}s]",flush=True)
