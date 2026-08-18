"""High-density LOGIC-BASED BENDERS (optimality-cut) prototype.

Master : block->bay assignment MIP.  min  w1*sum_j theta_j + w2*Z2 + w3*Z3
         theta_j is a surrogate lower bound on bay j's REAL tardiness.
Sub    : per-bay REAL crane scheduler (resched_bay = event-driven cranepack
         re-admission, the same v77-quality oracle).  Returns bay j's true
         tardiness T_j for the assigned set S_j.
Cut    : logic-based optimality (no-good) cut
             theta_j >= T_j * (1 - sum_{b in S_j}(1-x_bj) - sum_{b not in S_j} x_bj)
         i.e. binds only when the master reproduces exactly S_j.
Seed   : round 0 uses v77's own assignment so the oracle starts at v77 bays.
Each round we ALSO grade the realised full solution with utils and keep the
best feasible objective.  Reports whether Benders ever beats v77.

Usage: python3.12 hdbenders.py prob_38 [rounds=20] [step=4] [master_tl=10]
"""
import json, os, sys, time
import numpy as np
from collections import defaultdict
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
sys.path.insert(0, os.path.join(SP,"cc"))
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP
import gurobipy as gp
from gurobipy import GRB

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
ROUNDS=int(sys.argv[2]) if len(sys.argv)>2 else 20
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 4
MTL=float(sys.argv[4]) if len(sys.argv)>4 else 10.0
TLP=0.4
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
d=json.load(open(find(NAME))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays); w=d["weights"]
W1=float(w["w1"]); W2=float(w["w2"]); W3=float(w["w3"])
cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]; avg=sum(cap)/m; u=[avg/cap[j] for j in range(m)]
mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]; due=[B[b]["due_date"] for b in range(n)]

# ---- oracle machinery (from hdlns) ----
_olc={}; _wlc={}
def OL(b,o):
    if (b,o) not in _olc: _olc[(b,o)]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[(b,o)]
def WL(b,o,x,y):
    k=(b,o,x,y)
    if k not in _wlc: _wlc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=x,y=y,orient_idx=o).layers_at_pos()]
    return _wlc[k]
def obb(b,o): return M._orient_bbox(B[b],o)

def resched_bay(bay, blocks, wallcap=20.0):
    """Event-driven max-weighted-crane-fit admission. Returns {b:(o,x,y,en,ex)} or None."""
    W=bays[bay]["width"]; H=bays[bay]["height"]
    waiting=set(blocks); present={}; result={}
    if not blocks: return {}
    t=min(rel[b] for b in blocks); guard=0; tw=time.time()
    while waiting and guard<8000:
        if time.time()-tw>wallcap: return None
        guard+=1
        for b in [b for b,v in present.items() if v[4]<=t]: del present[b]
        avail=[b for b in waiting if rel[b]<=t]
        if not avail:
            nxt=min([rel[b] for b in waiting if rel[b]>t] or [t+1]); t=nxt; continue
        avail=sorted(avail,key=lambda b:(due[b],rel[b]))[:24]
        froz=[(WL(b,v[0],v[1],v[2]),int(v[3]),int(v[4])) for b,v in present.items()]
        binL=[]; wts=[]
        for b in avail:
            binL.append(([OL(b,o) for o in range(len(B[b]["shape"]))],
                         [tuple(float(v) for v in obb(b,o)) for o in range(len(B[b]["shape"]))],
                         [(int(t),int(t+pt[b]))]))
            slack=max(1,due[b]-t-pt[b]); wts.append(1000.0/slack)
        res=CP.pack(binL,float(W),float(H),STEP,TLP,seed=1,warm=None,frozen=froz,weights=wts)
        adm=0
        for (loc,o,x,y,en,ex) in res[1]:
            b=avail[loc]; present[b]=(o,x,y,t,t+pt[b]); result[b]=(o,x,y,t,t+pt[b]); waiting.discard(b); adm+=1
        if adm==0:
            cands=[v[4] for v in present.values() if v[4]>t]+[rel[b] for b in waiting if rel[b]>t]
            if not cands: return None
            t=min(cands)
    if waiting: return None
    return result

def oracle(ext):
    """Given assignment ext[b]->bay, schedule each bay for real. Returns (per-bay tard, full placement dict) or None-bays."""
    bybay=defaultdict(list)
    for b in range(n): bybay[ext[b]].append(b)
    Tj=[0.0]*m; place={}; okbays=set()
    for j in range(m):
        r=resched_bay(j, bybay[j])
        if r is None:
            Tj[j]=None; continue
        okbays.add(j)
        tj=0.0
        for b,v in r.items():
            place[b]=dict(bay=j,oi=v[0],x=v[1],y=v[2],en=v[3],ex=v[4]); tj+=max(0,v[4]-due[b])
        Tj[j]=tj
    return Tj, place, okbays

def grade(place):
    if len(place)!=n: return None
    al=[{"block_id":b,"bay_id":place[b]["bay"],"orient_idx":place[b]["oi"],"x":place[b]["x"],"y":place[b]["y"],
         "entry_time":place[b]["en"],"exit_time":place[b]["ex"]} for b in range(n)]
    ck=check_feasibility(d,M._build_operations(al))
    return ck if ck["feasible"] else None

# ---- v77 baseline + its assignment (seed) ----
best=None; seedext=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best):
        best=ck["objective"]
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY": pl[op["block_id"]]=op["bay_id"]
        seedext=[pl[b] for b in range(n)]
print(f"{NAME}: v77 obj={best:.0f}  w1={int(W1)} w2={int(W2)} w3={int(W3)}  (LB-Benders rounds={ROUNDS} step={STEP})",flush=True)

# ---- master ----
md=gp.Model("ben"); md.setParam("OutputFlag",0); md.setParam("Threads",4); md.setParam("MIPFocus",1)
x={(b,j):md.addVar(vtype=GRB.BINARY,name=f"x_{b}_{j}") for b in range(n) for j in range(m)}
for b in range(n): md.addConstr(gp.quicksum(x[b,j] for j in range(m))==1)
load=[gp.quicksum(x[b,j]*float(B[b]["workload"]) for b in range(n)) for j in range(m)]
Mv=md.addVar(lb=0)
for j in range(m):
    for k in range(m):
        if j!=k: md.addConstr(Mv>=u[j]*load[j]-u[k]*load[k])
Z3=gp.quicksum(x[b,j]*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
theta=[md.addVar(lb=0) for j in range(m)]
md.setObjective(W1*gp.quicksum(theta)+W2*Mv+W3*Z3, GRB.MINIMIZE)

def add_cut(ext, Tj):
    for j in range(m):
        if Tj[j] is None or Tj[j]<=0: continue
        Sj=[b for b in range(n) if ext[b]==j]
        # indicator = 1 - sum_{b in Sj}(1-x_bj) - sum_{b not in Sj} x_bj  ; ==1 iff exact set reproduced
        ind = 1 - gp.quicksum(1-x[b,j] for b in Sj) - gp.quicksum(x[b,j] for b in range(n) if ext[b]!=j)
        md.addConstr(theta[j] >= Tj[j]*ind)

best_benders=None; cuts=0
ext=seedext
for rnd in range(ROUNDS):
    Tj, place, okbays = oracle(ext)
    nfail=sum(1 for j in range(m) if Tj[j] is None)
    ck = grade(place) if nfail==0 else None
    realobj = ck["objective"] if ck else None
    realZ1  = ck["obj1"] if ck else None
    if realobj is not None and (best_benders is None or realobj<best_benders):
        best_benders=realobj
    add_cut(ext, Tj); cuts+=sum(1 for j in range(m) if Tj[j] and Tj[j]>0)
    tag = (f"obj={realobj:.0f} Z1={realZ1:.0f}" if realobj is not None else f"{nfail} bays unscheduled")
    msg=""
    if realobj is not None:
        dd=best-realobj
        msg = f"WIN -{round(100*dd/best,2)}%" if dd>0 else f"+{round(realobj-best)}"
    print(f"  r{rnd}: real {tag}  bestBenders={best_benders if best_benders else '-'}  cuts={cuts}  {msg}",flush=True)
    # re-solve master for next assignment
    md.setParam("TimeLimit",MTL)
    md.optimize()
    if md.SolCount==0: print("    master infeasible; stop"); break
    newext=[next(j for j in range(m) if x[b,j].X>0.5) for b in range(n)]
    thetaLB=sum(theta[j].X for j in range(m))
    if newext==ext:
        print(f"    master repeats assignment (thetaLB={thetaLB:.0f}); converged/stuck; stop"); break
    ext=newext

verdict = (f"WIN -{round(100*(best-best_benders)/best,2)}%" if best_benders and best_benders<best else "no win")
print(f"\n{NAME}: v77={best:.0f}  Benders best={best_benders if best_benders else 'none'}  {verdict}",flush=True)
