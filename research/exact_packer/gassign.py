"""P3 headroom probe: the UNCONSTRAINED (packing-ignored) Z2+Z3 assignment optimum.

Low-density objective = w2*Z2(imbalance) + w3*Z3(preference), Z1=0.  Packing only
affects feasibility, which is LOOSE at low density.  So the pure assignment optimum
(ignore packing) is a valid LOWER BOUND on the achievable objective.  If v77's result
is far above this LB, our LBBD/VLNS is leaving assignment quality on the table and we
can push toward it; if it's near the LB, we're already near-optimal.

Solves exactly with Gurobi:
  x[b,j] in {0,1}, sum_j x=1 ;  load_j = sum_b x*workload
  Z2 = floor(max_{j!=k} |u_j load_j - u_k load_k|)  (M >= each diff; minimise M)
  Z3 = sum_b sum_j x*(maxpref_b - pref_b[j])
  min w2*M + w3*Z3   (floor applied to the reported Z2)
Usage: python3.12 gassign.py prob_20 prob_17 prob_18 prob_19 ...
"""
import json, os, sys, math, time
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import myalgorithm as M
from utils import check_feasibility
import gurobipy as gp
from gurobipy import GRB

def find(nm):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p

def assign_lb(d, tl=30.0):
    B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays); w=d["weights"]
    W2=float(w["w2"]); W3=float(w["w3"])
    cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
    avg=sum(cap)/m; u=[avg/cap[j] for j in range(m)]
    mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
    md=gp.Model("a"); md.setParam("OutputFlag",0); md.setParam("TimeLimit",tl); md.setParam("Threads",4); md.setParam("MIPGap",0.0)
    x={(b,j):md.addVar(vtype=GRB.BINARY) for b in range(n) for j in range(m)}
    for b in range(n): md.addConstr(gp.quicksum(x[b,j] for j in range(m))==1)
    load=[gp.quicksum(x[b,j]*float(B[b]["workload"]) for b in range(n)) for j in range(m)]
    Mv=md.addVar(lb=0)
    for j in range(m):
        for k in range(m):
            if j!=k: md.addConstr(Mv>=u[j]*load[j]-u[k]*load[k])
    Z3=gp.quicksum(x[b,j]*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    md.setObjective(W2*Mv+W3*Z3, GRB.MINIMIZE)
    md.optimize()
    ext=[next(j for j in range(m) if x[b,j].X>0.5) for b in range(n)]
    loads=[0.0]*m; o3=0.0
    for b in range(n):
        loads[ext[b]]+=B[b]["workload"]; o3+=mxp[b]-B[b]["bay_preferences"][ext[b]]
    ul=[u[j]*loads[j] for j in range(m)]; o2=math.floor(max(ul)-min(ul))
    lb_obj=W2*o2+W3*o3
    return lb_obj, o2, int(o3), md.status, md.MIPGap

names=sys.argv[1:] or ["prob_20","prob_17","prob_18","prob_19","prob_16"]
print(f"{'inst':8s} {'n':>4s} {'w2':>5s} {'w3':>5s} {'assignLB':>10s} {'Z2':>6s} {'Z3':>6s} {'v77_obj':>10s} {'headroom':>9s}")
for nm in names:
    d=json.load(open(find(nm)))
    t=time.time(); lb,o2,o3,st,gap=assign_lb(d, 30.0)
    # v77 achieved (best of 2)
    best=None
    for _ in range(2):
        sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
        if ck["feasible"] and (best is None or ck["objective"]<best): best=ck["objective"]
    hr=best-lb
    print(f"{nm:8s} {len(d['blocks']):>4d} {int(d['weights']['w2']):>5d} {int(d['weights']['w3']):>5d} "
          f"{lb:10.0f} {o2:>6d} {o3:>6d} {best:10.0f} {hr:9.0f}  gap={gap:.2f} [{time.time()-t:.0f}s]",flush=True)
