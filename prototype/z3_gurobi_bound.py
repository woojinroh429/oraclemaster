"""
Gurobi MIP: optimal bay-assignment lower bound for w2*Z2 + w3*Z3 (Z1=0 low-density).
RESEARCH ONLY (Gurobi not allowed in submission). Compares our realized Z3 to the
exact assignment-optimal Z3 under the necessary area-capacity constraint. If our
realized Z3 >> the MIP optimum, there is bay-assignment headroom (our CP-SAT isn't
reaching it); if ~equal, we are at the assignment floor.

Model:
  x[b,j] in {0,1}, sum_j x[b,j]=1                    (each block one bay)
  Z3 = sum_b sum_j x[b,j]*(maxpref[b]-pref[b][j])
  per bay j, per release-time t:  sum_{b present at t} x[b,j]*area[b] <= cap_j
     (necessary condition for a feasible packing at that instant)
  Z2 = max_j |u_j * load_j - u_k * load_k|            (linearized)
  minimize w2*Z2 + w3*Z3
"""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import gurobipy as gp
from gurobipy import GRB
import myalgorithm as M
from utils import check_feasibility

def amin(B,b):
    best=None
    for oi in range(len(B[b]["shape"])):
        L=B[b]["shape"][oi]["layers"]; xs=[q[0] for l in L for q in l]; ys=[q[1] for l in L for q in l]
        a=(max(xs)-min(xs))*(max(ys)-min(ys))
        if best is None or a<best: best=a
    return best

def solve_bound(path, cap_scale=1.0, verbose=False):
    inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]
    n=len(B); m=len(bays)
    w=inst.get("weights",{}); w2=w.get("w2",1.0); w3=w.get("w3",1.0)
    rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]
    area=[amin(B,b) for b in range(n)]
    cap=[bays[j]["width"]*bays[j]["height"]*cap_scale for j in range(m)]
    mx=[max(B[b]["bay_preferences"]) for b in range(n)]
    # workload-imbalance normaliser u_j = avgcap/cap_j (matches utils Z2 def approx)
    rawcap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
    avg=sum(rawcap)/m
    U=[avg/rawcap[j] for j in range(m)]
    wl=[B[b]["workload"] for b in range(n)]

    mdl=gp.Model("z3bound"); mdl.Params.OutputFlag=1 if verbose else 0
    mdl.Params.TimeLimit=120
    x=mdl.addVars(n,m,vtype=GRB.BINARY,name="x")
    for b in range(n): mdl.addConstr(gp.quicksum(x[b,j] for j in range(m))==1)
    # area capacity per bay per distinct release time
    times=sorted(set(rel))
    for j in range(m):
        for t in times:
            present=[b for b in range(n) if rel[b]<=t<rel[b]+pt[b]]
            if present:
                mdl.addConstr(gp.quicksum(x[b,j]*area[b] for b in present)<=cap[j])
    # Z2 linearization
    load=mdl.addVars(m,lb=0,name="load")
    for j in range(m): mdl.addConstr(load[j]==gp.quicksum(x[b,j]*wl[b] for b in range(n)))
    Zmax=mdl.addVar(lb=0,name="Zmax")
    for j in range(m):
        for k in range(m):
            if j!=k: mdl.addConstr(Zmax>=U[j]*load[j]-U[k]*load[k])
    Z3=gp.quicksum(x[b,j]*(mx[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    mdl.setObjective(w2*Zmax+w3*Z3, GRB.MINIMIZE)
    t0=time.time(); mdl.optimize(); dt=time.time()-t0
    z3opt=sum((mx[b]-B[b]["bay_preferences"][j])*(1 if x[b,j].X>0.5 else 0) for b in range(n) for j in range(m))
    return z3opt, mdl.ObjVal, mdl.ObjBound, dt, w2, w3

def main():
    probs=sys.argv[1:] or ["../data/training_instances/train/prob_20.json",
                           "../data/train/prob_22.json","../data/train/prob_24.json",
                           "../data/train/prob_29.json"]
    for path in probs:
        nm=os.path.basename(path).replace(".json","")
        inst=json.load(open(path))
        sol=M.algorithm(inst,60); ck=check_feasibility(inst,sol)
        realZ3=ck["obj3"]
        z3opt,obj,bound,dt,w2,w3=solve_bound(path)
        gap=100*(realZ3-z3opt)/max(1,realZ3)
        print(f"{nm}: realized Z3={realZ3:.0f} | MIP-optimal(area-relaxed) Z3={z3opt:.0f} "
              f"(bound obj={bound:.0f}, {dt:.0f}s) | headroom={gap:.1f}% (w3={w3:.0f} -> {w3*(realZ3-z3opt):.0f} obj)",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
