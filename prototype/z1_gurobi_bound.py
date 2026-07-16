"""
FRESH DIAGNOSTIC: Gurobi lower bound on TARDINESS (Z1) under area-capacity relaxation.
Decide bay + entry time for each block to MINIMIZE total tardiness, subject to per-bay
per-time AREA capacity (a necessary condition; crane packing is stricter). If this
optimistic bound is >> below our realized Z1, scheduling (delaying slack blocks / better
bay+time) has headroom. If the bound ~ our Z1, we're at the scheduling floor even ignoring
crane -> definitive. RESEARCH ONLY (Gurobi not in submission).
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

def bound(path, tl=180):
    inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
    rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]; due=[b["due_date"] for b in B]
    area=[amin(B,b) for b in range(n)]; cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
    H=max(due[b]+pt[b] for b in range(n))+2  # horizon
    mdl=gp.Model(); mdl.Params.OutputFlag=0; mdl.Params.TimeLimit=tl; mdl.Params.MIPGap=0.01
    # x[b,j,t]=1: block b enters bay j at time t (t in [rel_b, H-pt_b])
    x={}
    for b in range(n):
        for j in range(m):
            for t in range(rel[b], H-pt[b]+1):
                x[b,j,t]=mdl.addVar(vtype=GRB.BINARY)
    for b in range(n):
        mdl.addConstr(gp.quicksum(x[b,j,t] for j in range(m) for t in range(rel[b],H-pt[b]+1))==1)
    # area capacity per bay per time
    times=range(0,H)
    for j in range(m):
        for tau in times:
            terms=[x[b,j,t]*area[b] for b in range(n) for t in range(max(rel[b],tau-pt[b]+1),min(H-pt[b],tau)+1) if (b,j,t) in x]
            if terms: mdl.addConstr(gp.quicksum(terms)<=cap[j])
    # tardiness
    T=mdl.addVars(n,lb=0)
    for b in range(n):
        exitb=gp.quicksum(x[b,j,t]*(t+pt[b]) for j in range(m) for t in range(rel[b],H-pt[b]+1))
        mdl.addConstr(T[b]>=exitb-due[b])
    mdl.setObjective(gp.quicksum(T[b] for b in range(n)), GRB.MINIMIZE)
    t0=time.time(); mdl.optimize(); dt=time.time()-t0
    return mdl.ObjVal, mdl.ObjBound, mdl.Status, dt

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json"]):
        nm=os.path.basename(path).replace(".json","")
        inst=json.load(open(path))
        ck=check_feasibility(inst, M.algorithm(inst,60)); ourZ1=ck["obj1"]
        try:
            z1opt,z1lb,st,dt=bound(path)
            print(f"{nm}: our Z1={ourZ1:.0f} | Gurobi min-tardiness(area-relaxed)={z1opt:.0f} "
                  f"(LB={z1lb:.0f}, status={st}, {dt:.0f}s) | headroom={ourZ1-z1opt:.0f}",flush=True)
        except Exception as e:
            print(f"{nm}: our Z1={ourZ1:.0f} | Gurobi ERR {e}",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
