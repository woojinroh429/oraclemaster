"""Gurobi SCHEDULING layer (not nesting) with NoRel heuristic.

Lesson from hdlbbd: a full-bay-AREA capacity OVER-promises -> unrealisable schedule
-> loses.  Fix: cap each bay at the concurrent footprint area v77 DEMONSTRABLY
achieves (so any schedule under it is realisable), then ask Gurobi (with the NoRel
heuristic) to REORDER entry times within that achievable capacity to cut tardiness.

Assignment FIXED to v77's.  Per bay, time-indexed min-sum-tardiness MIP:
  s[b,t]=1 : block b enters at grid-time t ;  sum_t s[b,t]=1
  cumulative:  for each t,  sum_{present b} foot_b * s <= Cbar_j   (Cbar = v77 peak achieved)
  tard_b >= (entry_b + pt_b) - due_b
  min sum tard_b
NoRelHeurTime spends the budget on the NoRel primal heuristic (good for weak-LP MIPs).

Reports v77 Z1  vs  Gurobi-predicted Z1 (per bay).  If Gurobi predicts LOWER under the
ACHIEVABLE cap, there is reordering gain worth realising; if it just matches v77, the
greedy is already schedule-optimal.
Usage: python3.12 gsched.py prob_38 [grid=3] [bay_tl=25] [norelfrac=0.6]
"""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import myalgorithm as M
from utils import check_feasibility
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
GS  =int(sys.argv[2]) if len(sys.argv)>2 else 3
BTL =float(sys.argv[3]) if len(sys.argv)>3 else 25.0
NRF =float(sys.argv[4]) if len(sys.argv)>4 else 0.6
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
_far,_bcap,_fsc=M._footprint_areas(inst); area=[_far[b] for b in range(n)]

best=None
for _ in range(2):
    sol=M.algorithm(inst,30); ck=check_feasibility(inst,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY":
                    b=op["block_id"]; pl[b]=dict(bay=op["bay_id"],x=op["x"],y=op["y"],oi=op["orient_idx"],en=int(tk),ex=int(tk)+pt[b])
        best=(ck["objective"],ck["obj1"],pl)
_,z1v,place=best
print(f"{NAME}: v77 Z1={z1v:.0f}  (grid={GS} bayTL={BTL} norel={NRF})",flush=True)
bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)

def cbar(bl):
    """v77's peak concurrent footprint area in this bay (an ACHIEVABLE capacity)."""
    ev=sorted(set(place[b]["en"] for b in bl))
    best=0.0
    for t in ev:
        s=sum(area[b] for b in bl if place[b]["en"]<=t<place[b]["ex"])
        best=max(best,s)
    return best

def sched_bay(bl):
    C=cbar(bl)
    t0=min(rel[b] for b in bl); Hmax=max(due[b] for b in bl)+max(pt[b] for b in bl)
    grid=list(range(t0,Hmax+1,GS));
    if grid[-1]!=Hmax: grid.append(Hmax)
    mdl=gp.Model("s"); mdl.setParam("OutputFlag",0); mdl.setParam("TimeLimit",BTL)
    mdl.setParam("Threads",4); mdl.setParam("MIPGap",0.01)
    mdl.setParam("NoRelHeurTime", NRF*BTL)     # <-- the NoRel primal heuristic
    mdl.setParam("MIPFocus",1)
    s={}
    for b in bl:
        cand=[t for t in grid if t>=rel[b]]
        if not cand: cand=[grid[-1]]
        for t in cand: s[b,t]=mdl.addVar(vtype=GRB.BINARY)
        mdl.addConstr(gp.quicksum(s[b,t] for t in cand)==1)
    for t in grid:
        e=gp.quicksum(area[b]*s[b,ts] for (b,ts) in s if ts<=t<ts+pt[b])
        mdl.addConstr(e<=C)
    tard={}
    for b in bl:
        comp=gp.quicksum((ts+pt[b])*s[b,ts] for (bb,ts) in s if bb==b)
        tv=mdl.addVar(lb=0); mdl.addConstr(tv>=comp-due[b]); tard[b]=tv
    mdl.setObjective(gp.quicksum(tard.values()),GRB.MINIMIZE)
    # warm start from v77
    for b in bl:
        near=min((t for (bb,t) in s if bb==b), key=lambda t:abs(t-place[b]["en"]), default=None)
        for (bb,t) in s:
            if bb==b: s[b,t].Start=1.0 if t==near else 0.0
    mdl.optimize()
    if mdl.SolCount==0: return None,C
    ent={}
    for b in bl:
        for (bb,t) in s:
            if bb==b and s[b,t].X>0.5: ent[b]=t;break
    pz=sum(max(0,ent[b]+pt[b]-due[b]) for b in bl)
    return pz, C, ent

def realise_bay(bay, bl, ent):
    """EXACT ogc_fast engine (== utils): place in Gurobi-entry order, each at the
    earliest engine-feasible instant >= its Gurobi entry. Guaranteed utils-valid."""
    E=M._ogc_fast_engine(inst); E.clear_all()
    order=sorted(bl, key=lambda b:(ent[b], due[b])); res={}
    for b in order:
        t=max(ent[b], rel[b]); g=0; ok=False
        while not ok and g<800:
            g+=1; r=E.find_best_placement(b,[bay],[t])
            if r and r[0]:
                _,bj,o,x,y,en,ex=r; E.add(int(bj),b,int(o),float(x),float(y),int(en),int(ex))
                res[b]=(int(o),int(x),int(y),int(en),int(ex)); ok=True
            else: t+=1
        if not ok: res[b]=(place[b]["oi"],place[b]["x"],place[b]["y"],place[b]["en"],place[b]["ex"])
    return res

tot_v77=0; tot_pred=0; newplace={}
for j in range(m):
    bl=bybay[j]
    if not bl: continue
    v77z=sum(max(0,place[b]["ex"]-due[b]) for b in bl); tot_v77+=v77z
    tb=time.time(); pz,C,ent=sched_bay(bl)
    if pz is None:
        tot_pred+=v77z
        for b in bl: newplace[b]=(j,place[b]["oi"],place[b]["x"],place[b]["y"],place[b]["en"],place[b]["ex"])
        print(f"  bay{j}: master no-sol (C={C:.0f})",flush=True); continue
    tot_pred+=pz
    r=realise_bay(j,bl,ent)
    for b,v in r.items(): newplace[b]=(j,)+v
    rz=sum(max(0,newplace[b][5]-due[b]) for b in bl)
    print(f"  bay{j}: {len(bl)}blk  v77_Z1={v77z}  gurobi_pred={pz}  realised={rz}  Cbar={C:.0f}  "
          f"{'REAL GAIN -'+str(v77z-rz) if rz<v77z else '+'+str(rz-v77z)}  [{time.time()-tb:.0f}s]",flush=True)
al=[{"block_id":b,"bay_id":newplace[b][0],"orient_idx":newplace[b][1],"x":newplace[b][2],
     "y":newplace[b][3],"entry_time":newplace[b][4],"exit_time":newplace[b][5]} for b in range(n) if b in newplace]
ck=check_feasibility(inst,M._build_operations(al)) if len(al)==n else {"feasible":False}
print(f"\n{NAME}: v77 Z1={tot_v77}  gurobi_pred(total)={tot_pred} ({round(100*(tot_v77-tot_pred)/max(1,tot_v77),1)}%)",flush=True)
if ck.get("feasible"):
    d=z1v-ck['obj1']
    print(f"  REALISED(exact): Z1={ck['obj1']:.0f}  obj={ck['objective']:.0f}  "
          f"{'REAL WIN Z1 -'+str(round(d))+' ('+str(round(100*d/max(1,z1v),1))+'%)' if d>0 else 'no real gain ('+str(round(d))+')'}",flush=True)
else:
    print(f"  REALISED: INFEASIBLE/incomplete ({len(al)}/{n})",flush=True)
