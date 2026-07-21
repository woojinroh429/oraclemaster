# Validate pack_schedule: realise v77's OWN bay assignment; should reproduce ~87k Z1=0.
import json, os, sys, numpy as np
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
sys.path.insert(0, os.path.join(SP,"cc"))
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP
d=json.load(open(os.path.join(SP,"data/training_instances/train/prob_20.json"))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays)
rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]; due=[b["due_date"] for b in B]
sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
print(f"v77 actual obj={ck['objective']:.0f} Z1={ck['obj1']:.0f} Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f}",flush=True)
assign=[0]*n
for tk,lst in sol["operations"].items():
    for op in lst:
        if op.get("type")=="ENTRY": assign[op["block_id"]]=op["bay_id"]
_L={}
def lay(b,o):
    if (b,o) not in _L: _L[(b,o)]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _L[(b,o)]
blocks_in=[([lay(b,o) for o in range(len(B[b]["shape"]))],[tuple(float(v) for v in M._orient_bbox(B[b],o)) for o in range(len(B[b]["shape"]))]) for b in range(n)]
bays_in=[(float(bays[j]["width"]),float(bays[j]["height"])) for j in range(m)]
for step in [2,1]:
    pl,tard,placed,ontime=CP.pack_schedule(blocks_in,bays_in,assign,rel,pt,due,step)
    al=[{"block_id":b,"bay_id":pl[b][0],"orient_idx":pl[b][1],"x":pl[b][2],"y":pl[b][3],"entry_time":pl[b][4],"exit_time":pl[b][5]} for b in range(n) if pl[b][0]>=0]
    c=check_feasibility(d,M._build_operations(al)) if len(al)==n else {"feasible":False}
    if c.get("feasible"):
        print(f"  pack_schedule(v77 assign,step={step}): placed={placed}/{n} ontime={ontime} tard={tard:.0f}  UTILS obj={c['objective']:.0f} Z1={c['obj1']:.0f}  vs v77 {ck['objective']:.0f}",flush=True)
    else:
        print(f"  pack_schedule(v77 assign,step={step}): placed={placed}/{n} ontime={ontime} tard={tard:.0f}  UTILS infeasible(all={len(al)==n})",flush=True)
