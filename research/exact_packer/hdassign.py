"""High-density fresh angle: does a FREE bay assignment reduce Z1 vs v77's?
Gurobi joint assign+schedule (time-indexed), per-bay concurrency capacity = the peak
concurrent footprint area v77 ACHIEVES in that bay (achievable), min tardiness.
If predicted Z1 << v77, redistribution is a lever; if ~=, v77's assignment is already good.
"""
import json, os, sys, math, time
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
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
d=json.load(open(find(NAME))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
far,_bc,_sc=M._footprint_areas(d); ar=[far[b] for b in range(n)]
# v77 baseline (best of 2) + its per-bay achieved peak concurrent area (achievable cap)
best=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["obj1"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY": b=op["block_id"]; pl[b]=(op["bay_id"],int(tk),int(tk)+pt[b])
        best=(ck["obj1"],ck["objective"],pl)
z1v,objv,place=best
bybay=defaultdict(list)
for b in place: bybay[place[b][0]].append(b)
Cbar=[0.0]*m
for j in range(m):
    bl=bybay[j]; evs=sorted(set(place[b][1] for b in bl))
    for t in evs: Cbar[j]=max(Cbar[j], sum(ar[b] for b in bl if place[b][1]<=t<place[b][2]))
# which bays each block fits in (footprint bbox <= bay)
fits=[[j for j in range(m) if all(True for _ in [0]) ] for b in range(n)]
def blockfits(b,j):
    W=bays[j]["width"]; H=bays[j]["height"]
    for o in range(len(B[b]["shape"])):
        x0,y0,x1,y1=M._orient_bbox(B[b],o)
        if (x1-x0)<=W+1e-9 and (y1-y0)<=H+1e-9: return True
    return False
fits=[[j for j in range(m) if blockfits(b,j)] for b in range(n)]
print(f"{NAME}: v77 Z1={z1v:.0f} obj={objv:.0f}  Cbar={[round(c) for c in Cbar]}  (free-assign Gurobi, grid={GS})",flush=True)
t0=min(rel); Hmax=max(due)+max(pt); grid=list(range(t0,Hmax+1,GS))
md=gp.Model("fa"); md.setParam("OutputFlag",0); md.setParam("TimeLimit",60); md.setParam("Threads",4)
md.setParam("MIPGap",0.02); md.setParam("NoRelHeurTime",25); md.setParam("MIPFocus",1)
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
    comp=gp.quicksum((ts+pt[b])*s[b,jj,ts] for (bb,jj,ts) in s if bb==b)
    tv=md.addVar(lb=0); md.addConstr(tv>=comp-due[b]); T[b]=tv
md.setObjective(gp.quicksum(T.values()), GRB.MINIMIZE)
# warm from v77
for b in range(n):
    j0,e0,_=place[b]; near=min((t for t in grid if t>=rel[b]), key=lambda t:abs(t-e0), default=grid[-1])
    for (bb,jj,ts) in s:
        if bb==b: s[b,jj,ts].Start = 1.0 if (jj==j0 and ts==near) else 0.0
tt=time.time(); md.optimize()
predz1=sum(max(0, next(ts+pt[b] for (bb,jj,ts) in s if bb==b and s[b,jj,ts].X>0.5)-due[b]) for b in range(n)) if md.SolCount>0 else -1
print(f"  free-assign predicted Z1={predz1}  (vs v77 {z1v:.0f})  gap={md.MIPGap:.2f} [{time.time()-tt:.0f}s]  "
      f"{'REDISTRIB LEVER -'+str(round(100*(z1v-predz1)/max(1,z1v)))+'%' if predz1>=0 and predz1<z1v*0.9 else 'no room (v77 assign already good)'}",flush=True)
