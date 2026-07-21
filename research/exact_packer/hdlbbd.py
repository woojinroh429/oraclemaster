"""High-density prototype: Gurobi tardiness-scheduling MASTER + cranepack ORACLE.

Hypothesis: on high-density instances the entire tardiness (Z1) is congestion-
WAITING (floor Z1 = 0, i.e. every block could be on time with infinite
concurrency).  v77 places greedily one-by-one.  Question: can a global Gurobi
schedule that KNOWS the crane concurrency limit (via a cranepack-calibrated
cumulative capacity) admit more blocks concurrently -> earlier entries -> less
tardiness than the greedy?

Design (per bay, assignment FIXED from v77):
  MASTER  = Gurobi time-indexed min-sum-tardiness with a per-time AREA-cumulative
            capacity  C_j = W_j*H_j*eta  (eta calibrated so the master's peak
            concurrency matches what cranepack can actually realise).
  ORACLE  = cranepack: realise the master's entry schedule in 2D (place blocks in
            master-entry order at their master entry time; if a block does not
            crane-fit, slip it to the next feasible instant).  Realised entries
            >= master entries, so realised Z1 >= predicted; a tight eta keeps them
            close.  This is the LBBD feasibility step (cut = the slip).

Reports: v77 Z1  vs  master-predicted Z1  vs  cranepack-realised Z1.
Usage: python3.12 hdlbbd.py prob_38 [eta=0.85] [gridstep=3] [bay_tl=20]
"""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77"))
os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import numpy as np, myalgorithm as M
from utils import check_feasibility
import cranepack as CP
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict

NAME = sys.argv[1] if len(sys.argv)>1 else "prob_38"
ETA  = float(sys.argv[2]) if len(sys.argv)>2 else 0.85
GS   = int(sys.argv[3]) if len(sys.argv)>3 else 3      # time-grid coarsening
BTL  = float(sys.argv[4]) if len(sys.argv)>4 else 20.0 # gurobi TL per bay
CSTEP= int(sys.argv[5]) if len(sys.argv)>5 else 6      # cranepack grid step

def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
# TRUE footprint area (union of layers, min over orientations), scaled;
# bay_caps are the matching scaled bay areas.  Using bbox area over-estimates
# demand (irregular blocks) and makes a single big block violate capacity.
_far, _bcap, _fsc = M._footprint_areas(inst)
area=[_far[b] for b in range(n)]
def baycap(j): return _bcap[j]   # scaled bay area (matches `area` scaling)

# ---- baseline (v77): take the BEST of a few runs (variance guard) ----
best_ck=None; best_place=None
for _ in range(2):
    sol=M.algorithm(inst,30); ck=check_feasibility(inst,sol)
    if ck["feasible"] and (best_ck is None or ck["objective"]<best_ck["objective"]):
        best_ck=ck
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY":
                    b=op["block_id"]; pl[b]=dict(bay=op["bay_id"],x=op["x"],y=op["y"],oi=op["orient_idx"],en=int(tk),ex=int(tk)+pt[b])
        best_place=pl
ck0=best_ck; place=best_place
print(f"{NAME}: v77 baseline obj={ck0['objective']:.0f} Z1={ck0['obj1']:.0f}  (eta={ETA} grid={GS})",flush=True)
bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)

# ---- geometry helpers for cranepack realisation ----
_olc={}
def OL(bid,o):
    k=(bid,o)
    if k not in _olc: _olc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=bid,block_data=B[bid],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[k]
_wlc={}
def WL(bid,o,x,y):
    k=(bid,o,x,y)
    if k not in _wlc: _wlc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=bid,block_data=B[bid],x=x,y=y,orient_idx=o).layers_at_pos()]
    return _wlc[k]
def obb(b,o): return M._orient_bbox(B[b],o)

def master_bay(bay, blocks):
    """Gurobi time-indexed min-sum-tardiness with area-cumulative capacity.
    Returns {b: entry_time} or None."""
    W=bays[bay]["width"]; H=bays[bay]["height"]; C=baycap(bay)*ETA
    t0=min(rel[b] for b in blocks); Hmax=max(due[b] for b in blocks)+max(pt[b] for b in blocks)
    # coarse grid of candidate start instants
    grid=list(range(t0, Hmax+1, GS))
    if grid[-1]!=Hmax: grid.append(Hmax)
    gidx={t:i for i,t in enumerate(grid)}
    mdl=gp.Model("sched"); mdl.setParam("OutputFlag",0); mdl.setParam("TimeLimit",BTL); mdl.setParam("Threads",4); mdl.setParam("MIPGap",0.02)
    s={}   # s[b,t]=1 start block b at grid-time t
    for b in blocks:
        cand=[t for t in grid if t>=rel[b] and t+pt[b]<=Hmax+GS]
        if not cand: cand=[grid[-1]]
        for t in cand: s[b,t]=mdl.addVar(vtype=GRB.BINARY, name=f"s{b}_{t}")
        mdl.addConstr(gp.quicksum(s[b,t] for t in cand)==1)
    # cumulative: at each grid time t, sum area of present blocks <= C
    for t in grid:
        expr=gp.quicksum(area[b]*s[b,ts] for (b,ts) in s
                         if ts<=t<ts+pt[b])
        mdl.addConstr(expr <= C)
    # tardiness
    tard={}
    for b in blocks:
        comp=gp.quicksum((ts+pt[b])*s[b,ts] for (bb,ts) in s if bb==b)
        tv=mdl.addVar(lb=0,name=f"t{b}"); mdl.addConstr(tv>=comp-due[b]); tard[b]=tv
    mdl.setObjective(gp.quicksum(tard.values()), GRB.MINIMIZE)
    # warm start from v77
    for b in blocks:
        ev=place[b]["en"]; near=min((t for (bb,t) in s if bb==b), key=lambda t:abs(t-ev), default=None)
        for (bb,t) in s:
            if bb==b: s[b,t].Start = 1.0 if t==near else 0.0
    mdl.optimize()
    if mdl.SolCount==0:
        print(f"    [bay{bay} master status={mdl.status} solcount=0 C={C:.0f} maxarea={max(area[b] for b in blocks):.0f}]",flush=True)
        return None, None
    ent={}
    for b in blocks:
        for (bb,t) in s:
            if bb==b and s[b,t].X>0.5: ent[b]=t; break
    pred_z1=sum(max(0,ent[b]+pt[b]-due[b]) for b in blocks)
    return ent, pred_z1

def realise_bay(bay, blocks, ent):
    """Realise the master's entry schedule with the EXACT ogc_fast engine (== utils
    feasibility).  Place blocks in master-entry order; each block enters at the
    earliest engine-feasible instant >= its master entry time (slip if blocked).
    This removes the coarse-grid illusion: the result is guaranteed utils-valid, so
    the realised Z1 is the HONEST tardiness of the master's schedule.
    Returns {b:(o,x,y,en,ex)}."""
    E=M._ogc_fast_engine(inst); E.clear_all()
    order=sorted(blocks, key=lambda b:(ent[b], due[b]))
    result={}
    for b in order:
        t=max(ent[b], rel[b]); guard=0; placed=False
        # candidate instants: master-entry, then successive exit events / +1 slips
        while not placed and guard<600:
            guard+=1
            res=E.find_best_placement(b, [bay], [t])
            if res and res[0]:
                _,bj,o,x,y,en,ex=res
                E.add(int(bj),b,int(o),float(x),float(y),int(en),int(ex))
                result[b]=(int(o),int(x),int(y),int(en),int(ex)); placed=True
            else:
                t+=1
        if not placed:
            result[b]=(place[b]["oi"],place[b]["x"],place[b]["y"],place[b]["en"],place[b]["ex"])
    return result

t_all=time.time()
newplace={}; pred_total=0
for bay in range(m):
    bl=bybay[bay]
    if not bl: continue
    tb=time.time()
    ent,pz=master_bay(bay,bl)
    if ent is None:
        print(f"  bay{bay}: master FAILED, keep v77",flush=True)
        for b in bl: newplace[b]=(bay,place[b]["oi"],place[b]["x"],place[b]["y"],place[b]["en"],place[b]["ex"])
        continue
    pred_total+=pz
    r=realise_bay(bay,bl,ent)
    for b,v in r.items(): newplace[b]=(bay,)+v
    rz=sum(max(0,v[5]-due[b]) for b,v in {b:newplace[b] for b in bl}.items())
    v77z=sum(max(0,place[b]["ex"]-due[b]) for b in bl)
    print(f"  bay{bay}: {len(bl)}blk  v77_Z1={v77z}  master_pred={pz}  realised={rz}  [{time.time()-tb:.0f}s]",flush=True)

al=[{"block_id":b,"bay_id":newplace[b][0],"orient_idx":newplace[b][1],"x":newplace[b][2],
     "y":newplace[b][3],"entry_time":newplace[b][4],"exit_time":newplace[b][5]} for b in range(n) if b in newplace]
ck=check_feasibility(inst,M._build_operations(al)) if len(al)==n else {"feasible":False}
print(f"\n{NAME}: v77 Z1={ck0['obj1']:.0f} obj={ck0['objective']:.0f}")
if ck.get("feasible"):
    d=ck0['objective']-ck['objective']
    print(f"  LBBD  Z1={ck['obj1']:.0f} obj={ck['objective']:.0f}  master_pred_Z1={pred_total}  "
          f"delta_obj={d:+.0f} ({'WIN '+str(round(100*d/ck0['objective'],1))+'%' if d>0 else 'lose'})  [{time.time()-t_all:.0f}s]",flush=True)
else:
    print(f"  LBBD INFEASIBLE/incomplete ({len(al)}/{n})  [{time.time()-t_all:.0f}s]",flush=True)
    if len(al)==n:
        print(f"    stage={ck.get('stage')} #violations={len(ck.get('violations',[]))}")
        for v in ck.get("violations",[])[:6]: print("     ", v)
