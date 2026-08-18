"""P3 assignment LBBD: Gurobi (NoRel) master + pack_schedule crane-feasibility cut.

Master:  min w2 Z2 + w3 Z3  s.t. per-bay per-release-time footprint-area cumulative
         <= bay_area * capf[j]   (NoRelHeurTime on).
Oracle:  realise the assignment with the new engine cranepack.pack_schedule; if a bay
         has late blocks (crane over-subscribed), tighten capf[j] to the achieved
         on-time concurrent area / bay_area  (a crane-calibrated Benders cut).
Iterate; keep the best fully-on-time (Z1=0) assignment -> obj = w2 Z2 + w3 Z3.
Compare to v77.  Usage: python3.12 gp3.py prob_20 [rounds=12] [step=2]
"""
import json, os, sys, math, time
import numpy as np
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
sys.path.insert(0, os.path.join(SP,"cc"))
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP
import gurobipy as gp
from gurobipy import GRB

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
ROUNDS=int(sys.argv[2]) if len(sys.argv)>2 else 12
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 2
def find(nm):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
d=json.load(open(find(NAME))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays); w=d["weights"]
W2=float(w["w2"]); W3=float(w["w3"])
cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]; avg=sum(cap)/m; u=[avg/cap[j] for j in range(m)]
mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]; due=[B[b]["due_date"] for b in range(n)]
far,_bc,_sc=M._footprint_areas(d); ar=[far[b] for b in range(n)]

# engine block input
_L={}
def lay(b,o):
    if (b,o) not in _L: _L[(b,o)]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _L[(b,o)]
blocks_in=[([lay(b,o) for o in range(len(B[b]["shape"]))],[tuple(float(v) for v in M._orient_bbox(B[b],o)) for o in range(len(B[b]["shape"]))]) for b in range(n)]
bays_in=[(float(bays[j]["width"]),float(bays[j]["height"])) for j in range(m)]

def master(capf, tl=15.0):
    md=gp.Model("a"); md.setParam("OutputFlag",0); md.setParam("TimeLimit",tl); md.setParam("Threads",4)
    md.setParam("MIPGap",0.01); md.setParam("NoRelHeurTime",0.5*tl); md.setParam("MIPFocus",1)
    x={(b,j):md.addVar(vtype=GRB.BINARY) for b in range(n) for j in range(m)}
    for b in range(n): md.addConstr(gp.quicksum(x[b,j] for j in range(m))==1)
    load=[gp.quicksum(x[b,j]*float(B[b]["workload"]) for b in range(n)) for j in range(m)]
    Mv=md.addVar(lb=0)
    for j in range(m):
        for k in range(m):
            if j!=k: md.addConstr(Mv>=u[j]*load[j]-u[k]*load[k])
    Z3=gp.quicksum(x[b,j]*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    for j in range(m):
        for t in sorted(set(rel)):
            pres=[b for b in range(n) if rel[b]<=t<rel[b]+pt[b]]
            if pres: md.addConstr(gp.quicksum(x[b,j]*ar[b] for b in pres) <= _bc[j]*capf[j])
    md.setObjective(W2*Mv+W3*Z3, GRB.MINIMIZE); md.optimize()
    if md.SolCount==0: return None
    return [next(j for j in range(m) if x[b,j].X>0.5) for b in range(n)]

def realise(ext):
    pl,tard,placed,ontime=CP.pack_schedule(blocks_in,bays_in,ext,rel,pt,due,STEP)
    return pl,tard,placed,ontime

def theo(ext):
    loads=[0.0]*m; o3=0.0
    for b in range(n): loads[ext[b]]+=B[b]["workload"]; o3+=mxp[b]-B[b]["bay_preferences"][ext[b]]
    ul=[u[j]*loads[j] for j in range(m)]; return W2*math.floor(max(ul)-min(ul))+W3*o3

# v77 baseline
best=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best): best=ck["objective"]
print(f"{NAME}: v77 baseline obj={best:.0f}  (Gurobi+NoRel master + pack_schedule cut, step={STEP})",flush=True)

capf=[1.0]*m
best_feas=None
for rnd in range(ROUNDS):
    ext=master(capf)
    if ext is None: print(f"  r{rnd}: master infeasible"); break
    pl,tard,placed,ontime=realise(ext)
    th=theo(ext)
    # per-bay: which bays have late/unplaced blocks -> tighten
    bay_ok=[True]*m; bay_area_ontime=[0.0]*m
    # compute per-bay achieved on-time concurrent area (peak) from placements
    from collections import defaultdict
    bl=defaultdict(list)
    for b in range(n):
        if pl[b][0]>=0: bl[pl[b][0]].append((pl[b][4],pl[b][4]+pt[b],ar[b],pl[b][4]+pt[b]<=due[b]))
        else: bay_ok[ext[b]]=False
    for b in range(n):
        if pl[b][0]>=0 and pl[b][4]+pt[b]>due[b]: bay_ok[ext[b]]=False
    for j in range(m):
        evs=sorted(set([e for e,_,_,_ in bl[j]]))
        pk=0.0
        for t in evs:
            s=sum(a for e,x_,a,ot in bl[j] if e<=t<x_ and ot)
            pk=max(pk,s)
        bay_area_ontime[j]=pk
    allok = (placed==n) and (ontime==n)
    if allok:
        alg=[{"block_id":b,"bay_id":pl[b][0],"orient_idx":pl[b][1],"x":pl[b][2],"y":pl[b][3],"entry_time":pl[b][4],"exit_time":pl[b][5]} for b in range(n)]
        ck=check_feasibility(d,M._build_operations(alg))
        obj=ck["objective"] if ck["feasible"] else float("inf")
        tag="FEAS" if ck["feasible"] else "utils-infeas"
        print(f"  r{rnd}: theo={th:.0f} engine Z1={tard:.0f} ontime={ontime}/{n} -> {tag} obj={obj:.0f}",flush=True)
        if ck["feasible"] and (best_feas is None or obj<best_feas): best_feas=obj
    else:
        # tighten over-subscribed bays
        tightened=[]
        for j in range(m):
            if not bay_ok[j]:
                nf=bay_area_ontime[j]/_bc[j]*0.97
                if nf<capf[j]-1e-6: capf[j]=max(0.3,nf); tightened.append(j)
        print(f"  r{rnd}: theo={th:.0f} engine Z1={tard:.0f} ontime={ontime}/{n} placed={placed} -> tighten bays {tightened} capf={[round(c,2) for c in capf]}",flush=True)
        if not tightened:
            print("    no further tightening possible; stop"); break

print(f"\n{NAME}: v77={best:.0f}  LBBD best Z1=0 obj={best_feas if best_feas else 'none'}  "
      f"{('WIN -'+str(round(100*(best-best_feas)/best,1))+'%' if best_feas and best_feas<best else 'no win')}",flush=True)
