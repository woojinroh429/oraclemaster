"""LOW-DENSITY assignment LBBD with the REAL crane oracle (not area proxy).

Master : Gurobi  min w2*Z2 + w3*Z3  s.t. accumulated feasibility cuts.
Oracle : per-bay, resched_bay (event-driven cranepack) schedules the assigned
         set minimising tardiness.  A bay is crane-Z1=0-FEASIBLE iff its achieved
         tardiness is 0.  (Real crane feasibility, so no area evaporation.)
Cut    : if bay j is infeasible (resched Z1_j>0 or unseated), add BOTH
           (a) a no-good cut forbidding the exact over-subscribed set, and
           (b) an area upper bound = achieved on-time peak area (monotone,
               generalises to all supersets).
Loop until the master-optimal assignment is fully crane-Z1=0-feasible -> that
assignment's w2 Z2 + w3 Z3 is a (heuristic) crane-feasible optimum.  Compare to
v77's 87156.  If below, crane-feasible room below v77 exists.
Usage: python3.12 gp4.py prob_20 [rounds=25] [step=2]
"""
import json, os, sys, math, time
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

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
ROUNDS=int(sys.argv[2]) if len(sys.argv)>2 else 25
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 2
TLP=0.4
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

_olc={}; _wlc={}
def OL(b,o):
    if (b,o) not in _olc: _olc[(b,o)]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[(b,o)]
def WL(b,o,x,y):
    k=(b,o,x,y)
    if k not in _wlc: _wlc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=x,y=y,orient_idx=o).layers_at_pos()]
    return _wlc[k]
def obb(b,o): return M._orient_bbox(B[b],o)

def resched_bay(bay, blocks, wallcap=15.0):
    W=bays[bay]["width"]; H=bays[bay]["height"]
    if not blocks: return {}, 0.0
    waiting=set(blocks); present={}; result={}
    t=min(rel[b] for b in blocks); guard=0; tw=time.time()
    while waiting and guard<8000:
        if time.time()-tw>wallcap: return None, None
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
            if not cands: return None, None
            t=min(cands)
    if waiting: return None, None
    z1=sum(max(0,v[4]-due[b]) for b,v in result.items())
    return result, z1

def oracle(ext):
    bybay=defaultdict(list)
    for b in range(n): bybay[ext[b]].append(b)
    per_z1={}; per_ok={}; peakarea={}
    for j in range(m):
        r,z1=resched_bay(j, bybay[j])
        if r is None: per_ok[j]=False; per_z1[j]=None; peakarea[j]=None; continue
        per_z1[j]=z1; per_ok[j]=(z1<=0)
        # on-time peak area
        evs=sorted(set(v[3] for v in r.values()))
        pk=0.0
        for t in evs:
            s=sum(ar[b] for b,v in r.items() if v[3]<=t<v[4] and v[4]<=due[b])
            pk=max(pk,s)
        peakarea[j]=pk
    return per_z1, per_ok, peakarea, bybay

# v77 baseline
best=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best): best=ck["objective"]
print(f"{NAME}: v77={best:.0f}  w2={int(W2)} w3={int(W3)}  (REAL-oracle assignment LBBD, step={STEP})",flush=True)

md=gp.Model("lbbd"); md.setParam("OutputFlag",0); md.setParam("Threads",4); md.setParam("MIPGap",0.0)
x={(b,j):md.addVar(vtype=GRB.BINARY) for b in range(n) for j in range(m)}
for b in range(n): md.addConstr(gp.quicksum(x[b,j] for j in range(m))==1)
load=[gp.quicksum(x[b,j]*float(B[b]["workload"]) for b in range(n)) for j in range(m)]
Mv=md.addVar(lb=0)
for j in range(m):
    for k in range(m):
        if j!=k: md.addConstr(Mv>=u[j]*load[j]-u[k]*load[k])
Z3=gp.quicksum(x[b,j]*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
md.setObjective(W2*Mv+W3*Z3, GRB.MINIMIZE)

def theo(ext):
    loads=[0.0]*m; o3=0.0
    for b in range(n): loads[ext[b]]+=B[b]["workload"]; o3+=mxp[b]-B[b]["bay_preferences"][ext[b]]
    ul=[u[j]*loads[j] for j in range(m)]; return W2*math.floor(max(ul)-min(ul))+W3*o3

best_feas=None; ncut=0
for rnd in range(ROUNDS):
    md.setParam("TimeLimit",15.0); md.optimize()
    if md.SolCount==0: print(f"  r{rnd}: master infeasible; stop"); break
    ext=[next(j for j in range(m) if x[b,j].X>0.5) for b in range(n)]
    lb=W2*Mv.X+W3*sum(x[b,j].X*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    per_z1,per_ok,peakarea,bybay=oracle(ext)
    badbays=[j for j in range(m) if not per_ok[j]]
    if not badbays:
        # fully crane-Z1=0-feasible assignment -> its Z2+Z3 is a feasible optimum
        th=theo(ext)
        if best_feas is None or th<best_feas: best_feas=th
        print(f"  r{rnd}: masterLB={lb:.0f} -> ALL BAYS Z1=0 FEASIBLE  obj={th:.0f}  "
              f"{'WIN -'+str(round(100*(best-th)/best,1))+'%' if th<best else '+'+str(round(th-best))}  cuts={ncut}",flush=True)
        break
    # add cuts for bad bays
    for j in badbays:
        Sj=bybay[j]
        md.addConstr(gp.quicksum(x[b,j] for b in Sj) <= len(Sj)-1); ncut+=1   # no-good
        if peakarea[j] is not None and peakarea[j]>0:
            # area upper bound at each release time (monotone, generalises)
            for t in sorted(set(rel)):
                pres=[b for b in range(n) if rel[b]<=t<rel[b]+pt[b]]
                if pres: md.addConstr(gp.quicksum(x[b,j]*ar[b] for b in pres) <= peakarea[j]*0.99); ncut+=1
    z1s={j:(round(per_z1[j],0) if per_z1[j] is not None else None) for j in badbays}
    print(f"  r{rnd}: masterLB={lb:.0f} badbays={badbays} bay-Z1={z1s} cuts={ncut}",flush=True)

verdict = (f"WIN -{round(100*(best-best_feas)/best,1)}%" if best_feas and best_feas<best else "no win / collapsed")
print(f"\n{NAME}: v77={best:.0f}  LBBD best crane-feasible obj={best_feas if best_feas else 'none'}  {verdict}",flush=True)
