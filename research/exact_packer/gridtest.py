"""H2 test: does a FINER grid / longer budget pack MORE concurrent blocks in prob_38's
binding window? If yes, our coarse-grid packer under-packs -> real DOF to gain."""
import json, os, sys, time, numpy as np
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
sys.path.insert(0, os.path.join(SP,"cc"))
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP
from collections import defaultdict
NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
BAY=int(sys.argv[2]) if len(sys.argv)>2 else 1
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
# v77 placement -> binding instant & pool
best=None
for _ in range(2):
    sol=M.algorithm(inst,30); ck=check_feasibility(inst,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY": b=op["block_id"]; pl[b]=dict(bay=op["bay_id"],en=int(tk),ex=int(tk)+pt[b])
        best=(ck["objective"],pl)
place=best[1]; bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)
bl=bybay[BAY]; ev=sorted(set(place[b]["en"] for b in bl))
def conc(t): return [b for b in bl if place[b]["en"]<=t<place[b]["ex"]]
tstar=max(ev,key=lambda t:len(conc(t))); v77cnt=len(conc(tstar))
pool=sorted([b for b in bl if rel[b]<=tstar], key=lambda b:due[b])[:40]
W=bays[BAY]["width"]; H=bays[BAY]["height"]
print(f"{NAME} bay{BAY} @t={tstar}: v77_concurrent={v77cnt} pool={len(pool)} bay={W}x{H}",flush=True)
_olc={}
def OL(bid,o):
    if (bid,o) not in _olc: _olc[(bid,o)]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=bid,block_data=B[bid],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[(bid,o)]
def obb(b,o): return M._orient_bbox(B[b],o)
binL=[]; 
for b in pool:
    binL.append(([OL(b,o) for o in range(len(B[b]["shape"]))],[tuple(float(v) for v in obb(b,o)) for o in range(len(B[b]["shape"]))],[(int(tstar),int(tstar+pt[b]))]))
for step in [6,4,2,1]:
    for bud in [3.0]:
        t0=time.time(); res=CP.pack(binL,float(W),float(H),step,bud,seed=1,warm=None,frozen=None)
        print(f"  cranepack step={step} bud={bud}: placed={len(res[1])}  (v77={v77cnt})  {'MORE +'+str(len(res[1])-v77cnt) if len(res[1])>v77cnt else ''}  [{time.time()-t0:.1f}s]",flush=True)
