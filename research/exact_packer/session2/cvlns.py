"""Test the C++ VLNS refiner (cranepack.refine) vs the Python VLNS: same warm, compare
final grader objective + iteration count + wall time."""
import json, os, sys, time
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v74")); sys.path.insert(0, os.path.join(SP,"cc"))
sys.path.insert(0, os.path.join(SP,"research"))
os.chdir(os.path.join(SP,"v74"))
import numpy as np, myalgorithm as M
from utils import check_feasibility
import cranepack as CP
import vlns as V

def find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
MODE=sys.argv[2] if len(sys.argv)>2 else "feedback"
BUD=float(sys.argv[3]) if len(sys.argv)>3 else 18.0
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
E=V.Engine(inst)
w2=float(inst["weights"]["w2"]); w3=float(inst["weights"]["w3"])

def as_tuple(a0):
    return {b:(a["bay_id"],a["orient_idx"],a["x"],a["y"],int(a["entry_time"]),int(a["exit_time"])) for b,a in a0.items()}
def score_tuple(a):
    sol=M._build_operations([{"block_id":b,"bay_id":v[0],"orient_idx":v[1],"x":v[2],"y":v[3],"entry_time":v[4],"exit_time":v[5]} for b,v in a.items()])
    ck=check_feasibility(inst,sol); return (ck["objective"] if ck["feasible"] else float("inf")), ck["feasible"]

# warm
res=M._exact_reassign(inst,E.bu,time.time()+10,mip_cap=6.0,mode=MODE)
warm=as_tuple({b:dict(v) for b,v in res[0].items()})
wo=score_tuple(warm)[0]

# ---- build refine inputs (per-block geometry) ----
blocks_in=[]
for b in range(n):
    ol=[[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos()] for o in range(len(B[b]["shape"]))]
    obb=[tuple(float(v) for v in M._orient_bbox(B[b],o)) for o in range(len(B[b]["shape"]))]
    blocks_in.append((ol,obb,int(B[b]["release_time"]),int(B[b]["processing_time"]),int(B[b]["due_date"]),
                      [float(p) for p in B[b]["bay_preferences"]], float(B[b]["workload"])))
baydims=[(float(bb["width"]),float(bb["height"])) for bb in bays]
bayunit=[float(x) for x in E.bu]
init=[tuple(int(x) for x in warm[b]) for b in range(n)]

# ---- C++ refine ----
t=time.time()
bestobj,outA,iters=CP.refine(blocks_in,baydims,bayunit,w2,w3,init,BUD,seed=7,WIN=6,NPULL=2,STEP=8)
tcpp=time.time()-t
cass={b:tuple(int(x) for x in outA[b]) for b in range(n)}
cverify,cfeas=score_tuple(cass)
print(f"{NAME}[{MODE}] warm={wo:.0f}")
print(f"  C++ refine : internal={bestobj:.0f} grader={cverify:.0f} feas={cfeas} iters={iters} [{tcpp:.1f}s]")

# ---- Python VLNS (same warm, same budget) ----
t=time.time()
best,fo,ff,it,ac,im=E.solve(time.time()+BUD, warm, seed=7, descent0=BUD*0.4)
tpy=time.time()-t
print(f"  Py  VLNS   : grader={fo:.0f} feas={ff} iters={it} [{tpy:.1f}s]")
print(f"  >>> C++ vs Py: {cverify:.0f} vs {fo:.0f}  ({iters} vs {it} iters, {iters/max(1,it):.1f}x)")
