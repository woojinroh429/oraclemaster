"""Conflict-graph Gurobi POC: EXACT crane feasibility (no area proxy), one bay.

For one bay's blocks (from v77's assignment): choose a candidate placement per block
and an entry time; the ONLY hard constraint is the exact crane conflict -- two blocks
whose union-of-layers footprints OVERLAP (at their chosen positions) cannot be time-
co-present (one always sweeps the other under the j>=k rule).  Minimise tardiness.

  y[b,k] in {0,1}  : block b uses candidate placement k   (sum_k y[b,k] = 1)
  e[b]  int        : entry time (>= release)
  For each footprint-overlapping candidate pair (b,k),(b2,k2):
     if both chosen -> intervals [e_b,e_b+pt_b) and [e_b2,e_b2+pt_b2) disjoint (big-M).
  min sum tardiness.
Because the constraint IS the exact crane rule, the Gurobi solution is crane-feasible
(no evaporation).  Compare its Z1 to v77's on this bay.
Usage: python3.12 cgraph.py prob_38 [bay=1] [ncand=5] [tl=60]
"""
import json, os, sys, time, itertools
import numpy as np
from shapely import Polygon, union_all
import shapely
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import myalgorithm as M
from utils import check_feasibility
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict
NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
BAY=int(sys.argv[2]) if len(sys.argv)>2 else 1
NCAND=int(sys.argv[3]) if len(sys.argv)>3 else 5
TL=float(sys.argv[4]) if len(sys.argv)>4 else 60.0
GRIDA=int(sys.argv[5]) if len(sys.argv)>5 else 12  # anchor grid for candidates
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
best=None
for _ in range(2):
    sol=M.algorithm(inst,30); ck=check_feasibility(inst,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY": b=op["block_id"]; pl[b]=(op["bay_id"],int(tk),int(tk)+pt[b])
        best=(ck["objective"],pl)
place=best[1]; bybay=defaultdict(list)
for b in place: bybay[place[b][0]].append(b)
bl=bybay[BAY]
v77_z1=sum(max(0,place[b][2]-due[b]) for b in bl)
W=bays[BAY]["width"]; H=bays[BAY]["height"]
print(f"{NAME} bay{BAY}: {len(bl)} blocks, bay={W}x{H}, v77 bay-Z1={v77_z1}  (ncand={NCAND} gridA={GRIDA})",flush=True)

# union-of-layers footprint polygon for (block,orient) at origin, and candidate placements
def foot_poly(b,o,x,y):
    layers=[np.asarray(L,dtype=float) for L in M.Block(block_id=b,block_data=B[b],x=x,y=y,orient_idx=o).layers_at_pos() if len(L)>=3]
    return union_all([Polygon(L).buffer(0) for L in layers])
# candidates: coarse anchor grid, feasible-in-empty-bay, pick a spread of NCAND
cands={}  # b -> list of (o,x,y, poly)
for b in bl:
    opts=[]
    for o in range(len(B[b]["shape"])):
        x0,y0,x1,y1=M._orient_bbox(B[b],o); w=x1-x0; h=y1-y0
        if w>W+1e-9 or h>H+1e-9: continue
        for ax in range(0, int(W-w)+1, GRIDA):
            for ay in range(0, int(H-h)+1, GRIDA):
                opts.append((o, ax-int(round(x0)), ay-int(round(y0))))
    # spread: take up to NCAND spread across opts
    if not opts: opts=[(0,0,0)]
    step=max(1,len(opts)//NCAND)
    chosen=opts[::step][:NCAND]
    cands[b]=[(o,x,y, foot_poly(b,o,x,y)) for (o,x,y) in chosen]

# footprint-overlap conflicts between candidate placements of different blocks
t0=time.time()
conf=[]  # (b,k,b2,k2)
blist=list(bl)
for i in range(len(blist)):
    b=blist[i]
    for j2 in range(i+1,len(blist)):
        b2=blist[j2]
        # time windows can't overlap? if rel/due force disjoint, skip. (they can overlap generally)
        for k,(o,x,y,pa) in enumerate(cands[b]):
            for k2,(o2,x2,y2,pb) in enumerate(cands[b2]):
                if pa.intersects(pb) and pa.intersection(pb).area>1e-6:
                    conf.append((b,k,b2,k2))
print(f"  candidates built, {len(conf)} position-conflict pairs  [{time.time()-t0:.0f}s]",flush=True)

md=gp.Model("cg"); md.setParam("OutputFlag",0); md.setParam("TimeLimit",TL); md.setParam("Threads",4)
md.setParam("MIPGap",0.03); md.setParam("NoRelHeurTime",TL*0.5); md.setParam("MIPFocus",1)
Hmax=max(due)+max(pt)
y={}; e={}
for b in bl:
    e[b]=md.addVar(lb=rel[b], ub=Hmax, vtype=GRB.INTEGER)
    for k in range(len(cands[b])): y[b,k]=md.addVar(vtype=GRB.BINARY)
    md.addConstr(gp.quicksum(y[b,k] for k in range(len(cands[b])))==1)
BIGM=Hmax+max(pt)+10
for (b,k,b2,k2) in conf:
    z=md.addVar(vtype=GRB.BINARY)  # z=1: b before b2
    # if both chosen: e_b+pt_b <= e_b2 (z=1) OR e_b2+pt_b2 <= e_b (z=0)
    md.addConstr(e[b]+pt[b] <= e[b2] + BIGM*(1-z) + BIGM*(2-y[b,k]-y[b2,k2]))
    md.addConstr(e[b2]+pt[b2] <= e[b] + BIGM*z + BIGM*(2-y[b,k]-y[b2,k2]))
T={}
for b in bl:
    T[b]=md.addVar(lb=0); md.addConstr(T[b] >= e[b]+pt[b]-due[b])
md.setObjective(gp.quicksum(T.values()), GRB.MINIMIZE)
# warm from v77
for b in bl:
    e[b].Start=place[b][1]
tt=time.time(); md.optimize()
if md.SolCount>0:
    z1=sum(max(0, round(e[b].X)+pt[b]-due[b]) for b in bl)
    print(f"  CGRAPH Gurobi: bay-Z1={z1}  (v77 {v77_z1})  bound={md.ObjBound:.0f} gap={md.MIPGap:.2f} [{time.time()-tt:.0f}s]  "
          f"{'WIN -'+str(round(100*(v77_z1-z1)/max(1,v77_z1)))+'%' if z1<v77_z1 else 'no win'}",flush=True)
else:
    print(f"  CGRAPH no solution [{time.time()-tt:.0f}s]",flush=True)
