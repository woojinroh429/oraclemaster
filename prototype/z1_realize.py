"""
Decisive: take Gurobi's Z1=0 (area-relaxed) bay assignment and REALIZE it with the
crane engine (engine picks positions + earliest feasible entry). If realized Z1 is
low, OUR bay assignment/scheduling was suboptimal (real lever). If realized Z1 ~ our
114+, the tardiness is a genuine crane-packing floor (area-optimum unrealizable).
"""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import gurobipy as gp
from gurobipy import GRB
import myalgorithm as M
from utils import check_feasibility
from z1_gurobi_bound import amin

def gurobi_assign(inst, tl=120):
    B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
    rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]; due=[b["due_date"] for b in B]
    area=[amin(B,b) for b in range(n)]; cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
    H=max(due[b]+pt[b] for b in range(n))+2
    mdl=gp.Model(); mdl.Params.OutputFlag=0; mdl.Params.TimeLimit=tl; mdl.Params.MIPGap=0.01
    x={}
    for b in range(n):
        for j in range(m):
            for t in range(rel[b],H-pt[b]+1): x[b,j,t]=mdl.addVar(vtype=GRB.BINARY)
    for b in range(n): mdl.addConstr(gp.quicksum(x[b,j,t] for j in range(m) for t in range(rel[b],H-pt[b]+1))==1)
    for j in range(m):
        for tau in range(0,H):
            terms=[x[b,j,t]*area[b] for b in range(n) for t in range(max(rel[b],tau-pt[b]+1),min(H-pt[b],tau)+1) if (b,j,t) in x]
            if terms: mdl.addConstr(gp.quicksum(terms)<=cap[j])
    T=mdl.addVars(n,lb=0)
    for b in range(n):
        exitb=gp.quicksum(x[b,j,t]*(t+pt[b]) for j in range(m) for t in range(rel[b],H-pt[b]+1))
        mdl.addConstr(T[b]>=exitb-due[b])
    mdl.setObjective(gp.quicksum(T[b] for b in range(n)), GRB.MINIMIZE); mdl.optimize()
    ext={}
    for b in range(n):
        for j in range(m):
            for t in range(rel[b],H-pt[b]+1):
                if (b,j,t) in x and x[b,j,t].X>0.5: ext[b]=j; break
    return ext, mdl.ObjVal

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json"]):
        nm=os.path.basename(path).replace(".json","")
        inst=json.load(open(path))
        ck0=check_feasibility(inst, M.algorithm(inst,60)); ourZ1=ck0["obj1"]; ourObj=ck0["objective"]
        ext,z1opt=gurobi_assign(inst)
        # realize the Gurobi bay assignment with the crane engine
        dl=time.time()+25
        try:
            recs=M._smallright_construct(inst, 25, step=1, mode="prefaware", ext_bay=ext)
            ok = recs and len(recs)==len(inst["blocks"])
        except Exception as e:
            recs=None; ok=False; err=e
        if ok:
            ck=check_feasibility(inst, M._build_operations([recs[b] for b in range(len(inst["blocks"]))]))
            print(f"{nm}: our Z1={ourZ1:.0f}(obj {ourObj:.0f}) | Gurobi area Z1=0 | "
                  f"REALIZED Gurobi-assign: Z1={ck['obj1']:.0f} Z3={ck['obj3']:.0f} obj={ck['objective']:.0f} "
                  f"feas={ck['feasible']}",flush=True)
        else:
            # spill realize fallback
            try:
                res=M._spill_realize(inst, ext, time.time()+20, fast=False)
                if res and res[1]:
                    ck=check_feasibility(inst, M._build_operations([res[1][b] for b in sorted(res[1])]))
                    print(f"{nm}: our Z1={ourZ1:.0f} | REALIZED(spill) Z1={ck['obj1']:.0f} obj={ck['objective']:.0f}",flush=True)
                else:
                    print(f"{nm}: our Z1={ourZ1:.0f} | realize failed (partial)",flush=True)
            except Exception as e:
                print(f"{nm}: our Z1={ourZ1:.0f} | realize ERR {e}",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
