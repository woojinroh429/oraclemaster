"""Test the NEW dense temporal engine (cranepack.pack_schedule) as the P3 realiser.
Realise the Gurobi Z2+Z3-optimal (and area-capped) assignments with the new engine;
if it seats all 300 on-time (Z1=0), the achieved objective = w2 Z2 + w3 Z3 (~40-52k),
far below v77's ~90-96k.
Usage: python3.12 gassignpack2.py prob_20 [step=2]
"""
import json, os, sys, math, time
import numpy as np
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
sys.path.insert(0, os.path.join(SP,"cc"))     # the freshly-built cranepack with pack_schedule
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP
import gurobipy as gp
from gurobipy import GRB

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
STEP=int(sys.argv[2]) if len(sys.argv)>2 else 2
def find(nm):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
d=json.load(open(find(NAME))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays); w=d["weights"]
W2=float(w["w2"]); W3=float(w["w3"])
cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]; avg=sum(cap)/m; u=[avg/cap[j] for j in range(m)]
mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]; due=[B[b]["due_date"] for b in range(n)]

print(f"{NAME}: n={n} m={m} w2={int(W2)} w3={int(W3)}  (engine=cranepack.pack_schedule step={STEP})",flush=True)
print("  cranepack exports:", [x for x in dir(CP) if not x.startswith("_")],flush=True)

# blocks input for pack_schedule
_layers={}
def layers(b,o):
    k=(b,o)
    if k not in _layers:
        _layers[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _layers[k]
blocks_in=[]
for b in range(n):
    no=len(B[b]["shape"])
    blocks_in.append(([layers(b,o) for o in range(no)],
                      [tuple(float(v) for v in M._orient_bbox(B[b],o)) for o in range(no)]))
bays_in=[(float(bays[j]["width"]),float(bays[j]["height"])) for j in range(m)]

def solve_assign(fact=None, tl=25.0):
    md=gp.Model("a"); md.setParam("OutputFlag",0); md.setParam("TimeLimit",tl); md.setParam("Threads",4); md.setParam("MIPGap",0.0)
    x={(b,j):md.addVar(vtype=GRB.BINARY) for b in range(n) for j in range(m)}
    for b in range(n): md.addConstr(gp.quicksum(x[b,j] for j in range(m))==1)
    load=[gp.quicksum(x[b,j]*float(B[b]["workload"]) for b in range(n)) for j in range(m)]
    Mv=md.addVar(lb=0)
    for j in range(m):
        for k in range(m):
            if j!=k: md.addConstr(Mv>=u[j]*load[j]-u[k]*load[k])
    Z3=gp.quicksum(x[b,j]*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    if fact is not None:
        far,_bc,_sc=M._footprint_areas(d); ar=[far[b] for b in range(n)]
        for j in range(m):
            for t in sorted(set(rel)):
                pres=[b for b in range(n) if rel[b]<=t<rel[b]+pt[b]]
                if pres: md.addConstr(gp.quicksum(x[b,j]*ar[b] for b in pres)<=_bc[j]*fact)
    md.setObjective(W2*Mv+W3*Z3, GRB.MINIMIZE); md.optimize()
    if md.SolCount==0: return None
    return [next(j for j in range(m) if x[b,j].X>0.5) for b in range(n)]

def theo(ext):
    loads=[0.0]*m; o3=0.0
    for b in range(n): loads[ext[b]]+=B[b]["workload"]; o3+=mxp[b]-B[b]["bay_preferences"][ext[b]]
    ul=[u[j]*loads[j] for j in range(m)]; return W2*math.floor(max(ul)-min(ul))+W3*o3, math.floor(max(ul)-min(ul)), int(o3)

# v77 baseline
best=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best): best=ck["objective"]
print(f"  v77 baseline obj={best:.0f}",flush=True)

for label,fact in [("UNCONSTR",None),("area1.0",1.0),("area0.85",0.85)]:
    t=time.time(); ext=solve_assign(fact,25.0)
    if ext is None: print(f"  [{label}] assign infeasible"); continue
    th,o2,o3=theo(ext)
    r=CP.pack_schedule(blocks_in, bays_in, ext, rel, pt, due, STEP)
    placements, tard, placed, ontime = r
    al=[{"block_id":b,"bay_id":placements[b][0],"orient_idx":placements[b][1],"x":placements[b][2],
         "y":placements[b][3],"entry_time":placements[b][4],"exit_time":placements[b][5]}
        for b in range(n) if placements[b][0]>=0]
    ck=check_feasibility(d, M._build_operations(al)) if len(al)==n else {"feasible":False,"stage":None}
    if ck.get("feasible"):
        d_=best-ck['objective']
        print(f"  [{label}] theo={th:.0f}(Z2={o2},Z3={o3})  engine: placed={placed}/{n} ontime={ontime} tard={tard:.0f}  "
              f"UTILS obj={ck['objective']:.0f} Z1={ck['obj1']:.0f}  "
              f"{'WIN -'+str(round(100*d_/best,1))+'%' if d_>0 else '+'+str(round(ck['objective']-best))}  [{time.time()-t:.0f}s]",flush=True)
    else:
        print(f"  [{label}] theo={th:.0f}  engine placed={placed}/{n} ontime={ontime} tard={tard:.0f}  "
              f"UTILS infeasible(stage={ck.get('stage')}, placed_all={len(al)==n})  [{time.time()-t:.0f}s]",flush=True)
