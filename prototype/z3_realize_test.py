"""
Decisive P3 test: take Gurobi's optimal (area-relaxed) bay assignment and try to
REALIZE it with our engine. If realized Z3 ~ MIP optimum with Z1 still 0, we have a
big realizable lever (our CP-SAT isn't reaching it). If realization blows up Z1 or
lands at high Z3, the area optimum is packing-unrealizable (floor).
Also reports what our own _exact_reassign CP-SAT assignment achieves, to see whether
the gap is CP-SAT-suboptimality (fixable) or realization-limited (floor).
"""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import gurobipy as gp
from gurobipy import GRB
import myalgorithm as M
from utils import check_feasibility
from z3_gurobi_bound import amin

def gurobi_assign(inst, tl=60):
    B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
    w=inst.get("weights",{}); w2=w.get("w2",1.0); w3=w.get("w3",1.0)
    rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]
    area=[amin(B,b) for b in range(n)]; rawcap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
    avg=sum(rawcap)/m; U=[avg/rawcap[j] for j in range(m)]; wl=[B[b]["workload"] for b in range(n)]
    mx=[max(B[b]["bay_preferences"]) for b in range(n)]
    mdl=gp.Model(); mdl.Params.OutputFlag=0; mdl.Params.TimeLimit=tl
    x=mdl.addVars(n,m,vtype=GRB.BINARY)
    for b in range(n): mdl.addConstr(gp.quicksum(x[b,j] for j in range(m))==1)
    for j in range(m):
        for t in sorted(set(rel)):
            pres=[b for b in range(n) if rel[b]<=t<rel[b]+pt[b]]
            if pres: mdl.addConstr(gp.quicksum(x[b,j]*area[b] for b in pres)<=rawcap[j])
    load=mdl.addVars(m,lb=0)
    for j in range(m): mdl.addConstr(load[j]==gp.quicksum(x[b,j]*wl[b] for b in range(n)))
    Zmax=mdl.addVar(lb=0)
    for j in range(m):
        for k in range(m):
            if j!=k: mdl.addConstr(Zmax>=U[j]*load[j]-U[k]*load[k])
    Z3=gp.quicksum(x[b,j]*(mx[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    mdl.setObjective(w2*Zmax+w3*Z3, GRB.MINIMIZE); mdl.optimize()
    ext={b: max(range(m), key=lambda j: x[b,j].X) for b in range(n)}
    z3opt=sum(mx[b]-B[b]["bay_preferences"][ext[b]] for b in range(n))
    return ext, z3opt

def realize(inst, ext, tl=30):
    """Realize bay assignment ext WITH spill (unplaceable blocks fall to other bays)
    via _spill_realize -> the proper repair, matching _exact_reassign's realizer."""
    dl=time.time()+tl
    try:
        res=M._spill_realize(inst, ext, dl, fast=False)
    except Exception as e:
        return None, f"spill-err:{e}"
    if res is None or res[1] is None: return None, "spill-none"
    assign=res[1]
    sol=M._build_operations([assign[b] for b in sorted(assign)])
    ck=check_feasibility(inst, sol)
    return ck, "ok"

def main():
    probs=sys.argv[1:] or ["../data/training_instances/train/prob_20.json"]
    for path in probs:
        nm=os.path.basename(path).replace(".json","")
        inst=json.load(open(path))
        base=check_feasibility(inst, M.algorithm(inst,60))
        ext,z3opt=gurobi_assign(inst)
        ck,status=realize(inst,ext)
        if ck and ck["feasible"]:
            print(f"{nm}: base Z3={base['obj3']:.0f}(obj {base['objective']:.0f}) | "
                  f"Gurobi-assign Z3opt={z3opt:.0f} -> REALIZED Z3={ck['obj3']:.0f} Z1={ck['obj1']:.0f} "
                  f"obj={ck['objective']:.0f} | realizable-gain vs base = {base['objective']-ck['objective']:.0f}",flush=True)
        else:
            print(f"{nm}: base Z3={base['obj3']:.0f} | Gurobi Z3opt={z3opt:.0f} -> REALIZE FAILED ({status})",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
