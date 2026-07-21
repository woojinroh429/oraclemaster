"""P3 lever test: does the Z2+Z3-OPTIMAL assignment actually crane-PACK?

Z2 (imbalance) and Z3 (preference) depend ONLY on the bay assignment, not on packing.
So if the unconstrained-optimal assignment (Gurobi, obj 40644 on prob_20) is crane-
packable on-time (Z1=0), the achieved objective is EXACTLY that 40644 -- far below v77's
87156 and top's ~81000.  The only question: does that assignment pack?

Test: Gurobi min-(w2 Z2 + w3 Z3) assignment -> force it via _smallright_construct(ext_bay)
-> grade.  Also tries a SEQUENCE of assignments trading a little balance for packability
(Gurobi with a per-bay max-count cap K, swept) to find the best PACKABLE assignment.
Usage: python3.12 gassignpack.py prob_20 [Kcap=0(=uncapped)]
"""
import json, os, sys, math, time
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v71")
import myalgorithm as M
from utils import check_feasibility
import gurobipy as gp
from gurobipy import GRB

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
def find(nm):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
d=json.load(open(find(NAME))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays); w=d["weights"]
W2=float(w["w2"]); W3=float(w["w3"])
cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
avg=sum(cap)/m; u=[avg/cap[j] for j in range(m)]
mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
rel=[bb["release_time"] for bb in B]; pt=[bb["processing_time"] for bb in B]

def solve_assign(peak_area_cap=None, tl=25.0):
    md=gp.Model("a"); md.setParam("OutputFlag",0); md.setParam("TimeLimit",tl); md.setParam("Threads",4); md.setParam("MIPGap",0.0)
    x={(b,j):md.addVar(vtype=GRB.BINARY) for b in range(n) for j in range(m)}
    for b in range(n): md.addConstr(gp.quicksum(x[b,j] for j in range(m))==1)
    load=[gp.quicksum(x[b,j]*float(B[b]["workload"]) for b in range(n)) for j in range(m)]
    Mv=md.addVar(lb=0)
    for j in range(m):
        for k in range(m):
            if j!=k: md.addConstr(Mv>=u[j]*load[j]-u[k]*load[k])
    Z3=gp.quicksum(x[b,j]*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    if peak_area_cap is not None:
        # per bay per release-time: concurrent footprint area <= cap*factor (LBBD-style)
        far,_bc,_sc=M._footprint_areas(d); ar=[far[b] for b in range(n)]
        for j in range(m):
            for t in sorted(set(rel)):
                pres=[b for b in range(n) if rel[b]<=t<rel[b]+pt[b]]
                if pres: md.addConstr(gp.quicksum(x[b,j]*ar[b] for b in pres) <= _bc[j]*peak_area_cap)
    md.setObjective(W2*Mv+W3*Z3, GRB.MINIMIZE)
    md.optimize()
    if md.SolCount==0: return None
    ext=[next(j for j in range(m) if x[b,j].X>0.5) for b in range(n)]
    return ext

def realize_and_grade(ext):
    """Force assignment via ext_bay, pack+schedule with v71 dense construction; SPILL any
    unplaced block into any feasible (bay,time) via the exact engine, then grade."""
    recs=M._smallright_construct(d, 40.0, step=1, mode="bigleft", ext_bay=ext)
    placed=set(recs.keys())
    if len(placed)<n:
        # rebuild the engine with the placed blocks, then spill the rest anywhere feasible
        E=M._ogc_fast_engine(d); E.clear_all()
        for b in placed:
            r=recs[b]; E.add(r["bay_id"],b,r["orient_idx"],float(r["x"]),float(r["y"]),int(r["entry_time"]),int(r["exit_time"]))
        for b in range(n):
            if b in placed: continue
            t=rel[b]; g=0; ok=False
            while not ok and g<2000:
                g+=1; rr=E.find_best_placement(b,list(range(m)),[t])
                if rr and rr[0]:
                    _,bj,o,x,y,en,ex=rr; E.add(int(bj),b,int(o),float(x),float(y),int(en),int(ex))
                    recs[b]={"block_id":b,"bay_id":int(bj),"orient_idx":int(o),"x":int(x),"y":int(y),"entry_time":int(en),"exit_time":int(ex)}
                    ok=True
                else: t+=1
    al=[{"block_id":b,"bay_id":recs[b]["bay_id"],"orient_idx":recs[b]["orient_idx"],
         "x":recs[b]["x"],"y":recs[b]["y"],"entry_time":recs[b]["entry_time"],
         "exit_time":recs[b]["exit_time"]} for b in range(n) if b in recs]
    if len(al)!=n: return None,len(al)
    return check_feasibility(d, M._build_operations(al)), len(al)

def theo(ext):
    loads=[0.0]*m; o3=0.0
    for b in range(n): loads[ext[b]]+=B[b]["workload"]; o3+=mxp[b]-B[b]["bay_preferences"][ext[b]]
    ul=[u[j]*loads[j] for j in range(m)]; o2=math.floor(max(ul)-min(ul))
    return W2*o2+W3*o3, o2, int(o3)

print(f"{NAME}: n={n} m={m} w2={int(W2)} w3={int(W3)}",flush=True)
# v77 baseline
best=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best): best=ck["objective"]
print(f"  v77 baseline obj={best:.0f}",flush=True)

for label,fact in [("UNCONSTR",None),("area1.0",1.0),("area0.85",0.85),("area0.70",0.70)]:
    t=time.time(); ext=solve_assign(fact, 25.0)
    if ext is None: print(f"  [{label}] assign infeasible"); continue
    th,o2,o3=theo(ext)
    ck,pl=realize_and_grade(ext)
    if ck and ck["feasible"]:
        print(f"  [{label}] assign_theo={th:.0f}(Z2={o2},Z3={o3})  PACKED obj={ck['objective']:.0f} Z1={ck['obj1']:.0f}  "
              f"{'vs v77 '+('WIN -'+str(round(100*(best-ck['objective'])/best,1))+'%' if ck['objective']<best else '+'+str(round(ck['objective']-best))) }  [{time.time()-t:.0f}s]",flush=True)
    else:
        print(f"  [{label}] assign_theo={th:.0f}(Z2={o2},Z3={o3})  NOT PACKABLE (placed {pl}/{n})  [{time.time()-t:.0f}s]",flush=True)
