"""Phase 1a: Gurobi master MIP for the low-density crane-feasible assignment.

Problem (Z1=0 regime): assign each block b to a bay j to minimise
    w2*Z2 + w3*Z3
  Z2 = floor(max_{j!=k} |u_j*load_j - u_k*load_k|),  load_j = sum workload of blocks in j
  Z3 = sum_b (maxpref_b - pref_b[assigned bay])
subject to CRANE-FEASIBILITY (there is an on-time crane packing).

Phase 1a only encodes the AREA relaxation (necessary cond) so we can verify the
Gurobi objective matches the existing CP-SAT area-relaxed optimum before adding
combinatorial crane cuts in Phase 2.
"""
import json, os, sys, math, time
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71"))
import myalgorithm as M
import gurobipy as gp
from gurobipy import GRB

def find(name):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,name+".json")
        if os.path.exists(p): return p

def build_master(d, capfac=None, tl=10.0, verbose=False):
    B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays)
    w=d["weights"]; W2=float(w["w2"]); W3=float(w["w3"])
    def amin(b):
        best=None
        for oi in range(len(B[b]["shape"])):
            bb=M._orient_bbox(B[b],oi); a=(bb[2]-bb[0])*(bb[3]-bb[1])
            if best is None or a<best: best=a
        return best
    area=[amin(b) for b in range(n)]
    cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
    rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]
    mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
    avg=sum(cap)/m
    u=[avg/cap[j] for j in range(m)]            # EXACT utils obj2 weights
    if capfac is None: capfac=[1.0]*m

    mdl=gp.Model("assign"); mdl.setParam("OutputFlag", 1 if verbose else 0)
    mdl.setParam("TimeLimit", tl); mdl.setParam("Threads", 4)
    x={(b,j): mdl.addVar(vtype=GRB.BINARY, name=f"x{b}_{j}") for b in range(n) for j in range(m)}
    for b in range(n):
        mdl.addConstr(gp.quicksum(x[b,j] for j in range(m))==1)
    load=[gp.quicksum(x[b,j]*float(B[b]["workload"]) for b in range(n)) for j in range(m)]
    # Z2 = max pairwise |u_j load_j - u_k load_k|  (continuous surrogate; floor applied after)
    Mv=mdl.addVar(lb=0, name="M")
    for j in range(m):
        for k in range(m):
            if j!=k: mdl.addConstr(Mv >= u[j]*load[j]-u[k]*load[k])
    Z3=gp.quicksum(x[b,j]*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    # per-bay per-release-time AREA capacity (necessary condition for Z1=0 packing)
    for j in range(m):
        for t in sorted(set(rel)):
            present=[b for b in range(n) if rel[b]<=t<rel[b]+pt[b]]
            if present:
                mdl.addConstr(gp.quicksum(x[b,j]*area[b] for b in present) <= cap[j]*capfac[j])
    mdl.setObjective(W2*Mv + W3*Z3, GRB.MINIMIZE)
    return mdl, x, (n,m,B,bays,area,u,W2,W3)

def solve_and_report(name):
    d=json.load(open(find(name)))
    t0=time.time()
    mdl,x,meta=build_master(d, tl=15.0)
    mdl.optimize()
    n,m,B,bays,area,u,W2,W3=meta
    ext=[next(j for j in range(m) if x[b,j].X>0.5) for b in range(n)]
    # recompute EXACT obj2/obj3 per utils
    loads=[0.0]*m; o3=0.0
    for b in range(n):
        loads[ext[b]]+=B[b]["workload"]; o3+=max(B[b]["bay_preferences"])-B[b]["bay_preferences"][ext[b]]
    ul=[u[j]*loads[j] for j in range(m)]; o2=math.floor(max(ul)-min(ul))
    w=d["weights"]
    print(f"{name}: Gurobi area-relaxed  Z2={o2} Z3={int(o3)}  w2Z2+w3Z3={w['w2']*o2+w['w3']*o3:.0f}  "
          f"status={mdl.status} gap={mdl.MIPGap:.3f} time={time.time()-t0:.1f}s", flush=True)

if __name__=="__main__":
    for nm in ["prob_13","prob_17","prob_20"]:
        solve_and_report(nm)
