"""Validate the high-density redistribution lever: force the free (Z1-min) assignment
into v71's dense construction (ext_bay) and grade the ACTUAL objective vs v77."""
import json, os, sys, math, time
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v71")
import myalgorithm as M
from utils import check_feasibility
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict
NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
GS=int(sys.argv[2]) if len(sys.argv)>2 else 4
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
d=json.load(open(find(NAME))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays); w=d["weights"]
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
far,_bc,_sc=M._footprint_areas(d); ar=[far[b] for b in range(n)]
# v77 baseline via full algorithm (v71≈v77 on HD)
best=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY": b=op["block_id"]; pl[b]=(op["bay_id"],int(tk),int(tk)+pt[b])
        best=(ck["objective"],ck["obj1"],ck["obj2"],ck["obj3"],pl)
objv,z1v,z2v,z3v,place=best
bybay=defaultdict(list)
for b in place: bybay[place[b][0]].append(b)
Cbar=[0.0]*m
for j in range(m):
    bl=bybay[j]; evs=sorted(set(place[b][1] for b in bl))
    for t in evs: Cbar[j]=max(Cbar[j], sum(ar[b] for b in bl if place[b][1]<=t<place[b][2]))
def blockfits(b,j):
    W=bays[j]["width"]; H=bays[j]["height"]
    for o in range(len(B[b]["shape"])):
        x0,y0,x1,y1=M._orient_bbox(B[b],o)
        if (x1-x0)<=W+1e-9 and (y1-y0)<=H+1e-9: return True
    return False
fits=[[j for j in range(m) if blockfits(b,j)] for b in range(n)]
print(f"{NAME}: v77 obj={objv:.0f} Z1={z1v:.0f} Z2={z2v:.0f} Z3={z3v:.0f}  Cbar={[round(c) for c in Cbar]}",flush=True)
# free-assign Gurobi: minimise w1*Z1 + w3*Z3 (include preference so redistribution stays cheap on Z3)
W1=float(w["w1"]); W3=float(w["w3"]); mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
t0=min(rel); Hmax=max(due)+max(pt); grid=list(range(t0,Hmax+1,GS))
md=gp.Model("fa"); md.setParam("OutputFlag",0); md.setParam("TimeLimit",50); md.setParam("Threads",4)
md.setParam("MIPGap",0.03); md.setParam("NoRelHeurTime",22); md.setParam("MIPFocus",1)
s={}
for b in range(n):
    cand=[(j,t) for j in fits[b] for t in grid if t>=rel[b]]
    for (j,t) in cand: s[b,j,t]=md.addVar(vtype=GRB.BINARY)
    md.addConstr(gp.quicksum(s[b,j,t] for (j,t) in cand)==1)
for j in range(m):
    for t in grid:
        md.addConstr(gp.quicksum(ar[b]*s[b,jj,ts] for (b,jj,ts) in s if jj==j and ts<=t<ts+pt[b]) <= Cbar[j]*1.05)
T={}
for b in range(n):
    comp=gp.quicksum((ts+pt[b])*s[b,jj,ts] for (bb,jj,ts) in s if bb==b); tv=md.addVar(lb=0); md.addConstr(tv>=comp-due[b]); T[b]=tv
Z3e=gp.quicksum(s[b,jj,ts]*(mxp[b]-B[b]["bay_preferences"][jj]) for (b,jj,ts) in s)
md.setObjective(W1*gp.quicksum(T.values())+W3*Z3e, GRB.MINIMIZE)
for b in range(n):
    j0,e0,_=place[b]; near=min((t for t in grid if t>=rel[b]), key=lambda t:abs(t-e0), default=grid[-1])
    for (bb,jj,ts) in s:
        if bb==b: s[b,jj,ts].Start=1.0 if (jj==j0 and ts==near) else 0.0
md.optimize()
if md.SolCount==0: print("  free-assign no sol"); sys.exit()
ext=[next(jj for (bb,jj,ts) in s if bb==b and s[b,jj,ts].X>0.5) for b in range(n)]
predz1=sum(max(0, next(ts+pt[b] for (bb,jj,ts) in s if bb==b and s[b,jj,ts].X>0.5)-due[b]) for b in range(n))
# how different from v77 assignment
diff=sum(1 for b in range(n) if ext[b]!=place[b][0])
print(f"  free-assign pred Z1={predz1} ({diff}/{n} blocks moved)  realising with ext_bay...",flush=True)
# REALISE: force ext_bay into v71 dense construction, best of a few modes, grade
bestobj=None; bestck=None
for mode,step in [("bigleft",2),("flatbl",2),("bigleft",1)]:
    recs=M._smallright_construct(d, 40.0, step=step, mode=mode, ext_bay=ext)
    al=[{"block_id":b,"bay_id":recs[b]["bay_id"],"orient_idx":recs[b]["orient_idx"],"x":recs[b]["x"],"y":recs[b]["y"],"entry_time":recs[b]["entry_time"],"exit_time":recs[b]["exit_time"]} for b in range(n) if b in recs]
    if len(al)!=n: 
        print(f"    {mode} step{step}: placed {len(al)}/{n}"); continue
    ck=check_feasibility(d,M._build_operations(al))
    if ck["feasible"] and (bestobj is None or ck["objective"]<bestobj): bestobj=ck["objective"]; bestck=ck
    print(f"    realise {mode} step{step}: {'obj=%.0f Z1=%.0f Z3=%.0f'%(ck['objective'],ck['obj1'],ck['obj3']) if ck['feasible'] else 'infeas'}",flush=True)
if bestobj is not None:
    print(f"  RESULT: v77 obj={objv:.0f}  free-assign realised obj={bestobj:.0f}  "
          f"{'WIN -'+str(round(100*(objv-bestobj)/objv,1))+'%' if bestobj<objv else '+'+str(round(bestobj-objv))+' (lose)'}",flush=True)
