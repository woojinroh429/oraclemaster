# Feedback-refinement on pack_schedule: boost late blocks' priority, re-run, keep best.
# Target: reach Z1=0 on v77's OWN (known Z1=0-packable) assignment -> proves the engine
# can be a strong oracle.
import json, os, sys, numpy as np
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
sys.path.insert(0, os.path.join(SP,"cc"))
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP
NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
STEP=int(sys.argv[2]) if len(sys.argv)>2 else 1
ITERS=int(sys.argv[3]) if len(sys.argv)>3 else 20
def find(nm):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
d=json.load(open(find(NAME))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays)
rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]; due=[b["due_date"] for b in B]
sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
assign=[0]*n
for tk,lst in sol["operations"].items():
    for op in lst:
        if op.get("type")=="ENTRY": assign[op["block_id"]]=op["bay_id"]
print(f"{NAME}: v77 obj={ck['objective']:.0f} Z1={ck['obj1']:.0f}",flush=True)
_L={}
def lay(b,o):
    if (b,o) not in _L: _L[(b,o)]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _L[(b,o)]
blocks_in=[([lay(b,o) for o in range(len(B[b]["shape"]))],[tuple(float(v) for v in M._orient_bbox(B[b],o)) for o in range(len(B[b]["shape"]))]) for b in range(n)]
bays_in=[(float(bays[j]["width"]),float(bays[j]["height"])) for j in range(m)]

prio=[float(due[b]) for b in range(n)]
best_tard=1e18; best_pl=None; best_ontime=0
for it in range(ITERS):
    pl,tard,placed,ontime=CP.pack_schedule(blocks_in,bays_in,assign,rel,pt,due,STEP,prio)
    if tard<best_tard: best_tard=tard; best_pl=pl; best_ontime=ontime
    # boost late blocks: lower their prio (admit earlier)
    nlate=0
    for b in range(n):
        if pl[b][0]>=0 and pl[b][5]>due[b]:
            late=pl[b][5]-due[b]; prio[b]-= (late+1)*3.0; nlate+=1
        elif pl[b][0]<0:
            prio[b]-=50.0; nlate+=1
    print(f"  it{it}: placed={placed}/{n} ontime={ontime} tard={tard:.0f} (late={nlate})",flush=True)
    if tard==0 and placed==n: break
# grade best
al=[{"block_id":b,"bay_id":best_pl[b][0],"orient_idx":best_pl[b][1],"x":best_pl[b][2],"y":best_pl[b][3],"entry_time":best_pl[b][4],"exit_time":best_pl[b][5]} for b in range(n) if best_pl[b][0]>=0]
c=check_feasibility(d,M._build_operations(al)) if len(al)==n else {"feasible":False}
print(f"  BEST: tard={best_tard:.0f} ontime={best_ontime}/{n}  "
      + (f"UTILS obj={c['objective']:.0f} Z1={c['obj1']:.0f} vs v77 {ck['objective']:.0f}" if c.get("feasible") else f"infeas(all={len(al)==n})"),flush=True)
