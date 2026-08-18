"""Phase 2: Logic-Based Benders with COMBINATORIAL crane cuts (Gurobi master).

Loop:
  1. master.optimize() -> assignment ext (min w2Z2+w3Z3 s.t. accumulated cuts)
  2. crane_oracle(ext): real forced-bay packing.
       - feasible (Z1=0): record candidate (ext, real obj).  Its obj is a valid
         upper bound; the master obj is a valid lower bound -> if they meet, OPTIMAL.
       - infeasible: add cut  sum_{b in S} x[b,j] <= |S|-1  and continue.
  3. Also SPILL-REPAIR each infeasible ext to get a feasible candidate anyway
     (so we always have an incumbent even before the cuts converge).
Stops on optimality (LB==UB), time budget, or cut stall.
"""
import os, sys, time, json, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"research"))
import myalgorithm as M
from utils import check_feasibility
import gurobipy as gp
from gurobipy import GRB
from gmaster import build_master, find
from oracle import crane_oracle

def real_obj(d, ext):
    """spill-realise ext -> a guaranteed-feasible candidate obj (or inf)."""
    try:
        bu=M._bay_unit_weights(d["bays"])
        sr=M._spill_realize(d, ext, time.time()+5.0, fast=False)
        if sr is not None:
            return sr[0], sr[1]
    except Exception:
        pass
    return float("inf"), None

def lbbd(name, budget=30.0, verbose=True):
    d=json.load(open(find(name))); w=d["weights"]
    t0=time.time()
    mdl,x,meta=build_master(d, tl=5.0)
    n,m,B,bays,area,u,W2,W3=meta
    best_obj=float("inf"); best_ext=None; it=0; ncut=0
    while time.time()-t0 < budget:
        it+=1
        mdl.setParam("TimeLimit", max(1.0, min(5.0, budget-(time.time()-t0)-1.0)))
        mdl.optimize()
        if mdl.SolCount==0: break
        lb=mdl.ObjVal
        ext=[next(j for j in range(m) if x[b,j].X>0.5) for b in range(n)]
        feas,core,o1,sol=crane_oracle(d, ext, deadline_s=4.0)
        if feas:
            r=check_feasibility(d, sol); ob=r["objective"]
            if ob<best_obj: best_obj=ob; best_ext=ext
            if verbose: print(f"  it{it}: FEASIBLE obj={ob:.0f} LB={lb:.0f} gap={100*(ob-lb)/max(1,ob):.1f}% cuts={ncut} t={time.time()-t0:.1f}s", flush=True)
            if ob <= lb+0.5: break   # optimality
            # still add a cut to force exploration of other assignments? No: feasible+optimal-enough
            break
        else:
            # spill-repair fallback candidate (always feasible)
            ro, _ = real_obj(d, ext)
            if ro<best_obj: best_obj=ro; best_ext=ext
            if core is not None:
                j,S=core
                mdl.addConstr(gp.quicksum(x[b,j] for b in S) <= len(S)-1)
                ncut+=1
            if verbose and it<=40: print(f"  it{it}: infeas core=(bay{core[0]},|S|={len(core[1])}) LB={lb:.0f} incumbent={best_obj:.0f} cuts={ncut} t={time.time()-t0:.1f}s", flush=True)
            if core is None: break
    return best_obj, ncut, it, time.time()-t0

if __name__=="__main__":
    TARGET={"prob_13":73480,"prob_17":57222,"prob_20":86779}
    for nm in (sys.argv[1:] or ["prob_20","prob_13","prob_17"]):
        o,nc,it,dt=lbbd(nm, budget=30.0)
        tg=TARGET.get(nm,0)
        print(f"== {nm}: LBBD obj={o:.0f}  (pipeline@120s floor={tg})  cuts={nc} iters={it} time={dt:.1f}s ==", flush=True)
