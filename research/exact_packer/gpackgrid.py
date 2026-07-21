"""Gurobi GRID SET-PACKING for one congested bay-window (the "Gurobi done right"
test).  Instead of naive big-M pairwise no-overlap (weak LP -> 36s timeout), model
placement as a cell set-packing:

  y[b,o,p] = 1  : block b, orientation o, anchored at grid cell p
  (1) each block placed at most once :  sum_{o,p} y[b,o,p] <= 1
  (2) each cell covered at most once :  sum_{(b,o,p) covering cell c} y[b,o,p] <= 1
  max  sum w_b * y[b,o,p]

Constraint (2) is a set-packing matrix -> TIGHT LP relaxation + Gurobi clique cuts,
unlike big-M.  For blocks all present in the same instant the crane rule reduces to
"union-of-layers footprints must not overlap" (each sweeps the other), so cell
packing on the union footprint IS the crane constraint for the concurrency question.

Measures: how many blocks Gurobi co-places (vs v77=27, cranepack=26 on prob_38 bay1)
and how fast, at grid step g.  Not full optimality -- a good feasible fast is the goal.

Usage: python3.12 gpackgrid.py prob_38 [bay=1] [g=2] [TL=20]
"""
import json, os, sys, time
import numpy as np
import shapely
from shapely import Polygon, points, contains, union_all
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import myalgorithm as M
from utils import check_feasibility
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
BAY =int(sys.argv[2]) if len(sys.argv)>2 else 1
G   =float(sys.argv[3]) if len(sys.argv)>3 else 2.0
TL  =float(sys.argv[4]) if len(sys.argv)>4 else 20.0
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]

# ---- v77 baseline placement (best-of-2), to define the binding instant & pool ----
best=None
for _ in range(2):
    sol=M.algorithm(inst,30); ck=check_feasibility(inst,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY":
                    b=op["block_id"]; pl[b]=dict(bay=op["bay_id"],en=int(tk),ex=int(tk)+pt[b])
        best=(ck["objective"],ck["obj1"],pl)
_,z1,place=best
bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)
bl=bybay[BAY]
ev=sorted(set(place[b]["en"] for b in bl))
def conc(t): return [b for b in bl if place[b]["en"]<=t<place[b]["ex"]]
tstar=max(ev,key=lambda t:len(conc(t))); v77cnt=len(conc(tstar))
pool=sorted([b for b in bl if rel[b]<=tstar], key=lambda b:due[b])[:40]
W=bays[BAY]["width"]; H=bays[BAY]["height"]
print(f"{NAME} bay{BAY} @t={tstar}: v77_concurrent={v77cnt}  pool={len(pool)}  bay={W}x{H}  grid_step={G}",flush=True)

# ---- grid ----
NX=int(np.floor(W/G)); NY=int(np.floor(H/G))
cx=(np.arange(NX)+0.5)*G; cy=(np.arange(NY)+0.5)*G
CX,CY=np.meshgrid(cx,cy,indexing="ij")   # (NX,NY)
CELLPTS=points(CX.ravel(),CY.ravel())    # NX*NY points

def footprint_mask(b,o):
    """Relative covered-cell offset set (ci,cj) when the footprint bbox-min is at the
    origin cell, plus footprint cell-size (ncx,ncy)."""
    layers=[np.asarray(L,dtype=float) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos() if len(L)>=3]
    if not layers: return None
    polys=[Polygon(L) for L in layers]
    uni=union_all([p.buffer(0) for p in polys])   # union of layers (buffer0 fixes tiny invalids)
    x0,y0,x1,y1=uni.bounds
    fw=x1-x0; fh=y1-y0
    if fw>W+1e-6 or fh>H+1e-6: return None
    ncx=int(np.ceil(fw/G))+1; ncy=int(np.ceil(fh/G))+1
    # local cell centers (footprint min corner at origin)
    lx=(np.arange(ncx)+0.5)*G; ly=(np.arange(ncy)+0.5)*G
    LX,LY=np.meshgrid(lx,ly,indexing="ij")
    # translate footprint so bbox-min at origin
    uni2=shapely.transform(uni, lambda a: a-[x0,y0])
    m=contains(uni2, points(LX.ravel(),LY.ravel())).reshape(ncx,ncy)
    offs=[(int(i),int(j)) for i in range(ncx) for j in range(ncy) if m[i,j]]
    if not offs: offs=[(0,0)]   # degenerate tiny block: reserve its origin cell
    return offs, ncx, ncy

t_build=time.time()
mdl=gp.Model("gridpack"); mdl.setParam("OutputFlag",0)
mdl.setParam("TimeLimit",TL); mdl.setParam("Threads",4)
mdl.setParam("MIPFocus",1); mdl.setParam("Presolve",2); mdl.setParam("Symmetry",2)
mdl.setParam("Cuts",2); mdl.setParam("MIPGap",0.0)
cell_vars=defaultdict(list)   # cell index -> list of vars covering it
block_vars=defaultdict(list)  # b -> list of vars
nvars=0
for b in pool:
    fm=footprint_mask(b, 0)  # use orient with min area? try a few orients
    orients=range(len(B[b]["shape"]))
    for o in orients:
        r=footprint_mask(b,o)
        if r is None: continue
        offs,ncx,ncy=r
        for I in range(0, NX-ncx+1):
            for J in range(0, NY-ncy+1):
                cells=[(I+ci)*NY+(J+cj) for (ci,cj) in offs if I+ci<NX and J+cj<NY]
                if len(cells)!=len(offs): continue
                v=mdl.addVar(vtype=GRB.BINARY); nvars+=1
                block_vars[b].append(v)
                for c in cells: cell_vars[c].append(v)
for b in pool:
    if block_vars[b]: mdl.addConstr(gp.quicksum(block_vars[b])<=1)
for c,vs in cell_vars.items():
    if len(vs)>1: mdl.addConstr(gp.quicksum(vs)<=1)
mdl.setObjective(gp.quicksum(v for vs in block_vars.values() for v in vs), GRB.MAXIMIZE)
build_t=time.time()-t_build
t_opt=time.time()
mdl.optimize()
opt_t=time.time()-t_opt
placed=int(round(mdl.ObjVal)) if mdl.SolCount>0 else 0
bound=mdl.ObjBound if mdl.SolCount>0 else float("nan")
print(f"  GUROBI grid set-packing: placed={placed}  bound={bound:.1f}  gap={mdl.MIPGap:.3f}  "
      f"vars={nvars} cells={len(cell_vars)}  build={build_t:.1f}s solve={opt_t:.1f}s  status={mdl.status}",flush=True)
print(f"  COMPARE: v77={v77cnt}  cranepack=26(prior)  gurobi={placed}  "
      f"{'GUROBI WINS +'+str(placed-v77cnt) if placed>v77cnt else ('tie' if placed==v77cnt else 'gurobi -'+str(v77cnt-placed))}",flush=True)
