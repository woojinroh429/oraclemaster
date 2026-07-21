"""Clean controlled test of the Gurobi-schedule lever, isolating it from realiser
quality by using the SAME dense packer (v71 _smallright_construct, mode=bigleft)
for both the baseline and the Gurobi-scheduled realisation.

  A = _smallright_construct(bigleft)                      # v71 greedy schedule+pack
  B = _smallright_construct(bigleft, ext_bay=A_assign,    # same packer, but dispatch
                            ext_entry=Gurobi_schedule)    #   order = Gurobi's schedule

Gurobi schedule: per bay (A's assignment fixed), time-indexed min-tardiness with a
per-time footprint-area cumulative capacity = A's achieved peak concurrent area
(achievable), NoRel heuristic on.  If B's Z1 < A's, the schedule lever is real and
capturable with a v77-quality packer.
Usage: python3.12 gsched2.py prob_38 [grid=3] [bayTL=25]
"""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v71")
import myalgorithm as M
from utils import check_feasibility
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
GS  =int(sys.argv[2]) if len(sys.argv)>2 else 3
BTL =float(sys.argv[3]) if len(sys.argv)>3 else 25.0
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
_far,_bcap,_fsc=M._footprint_areas(inst); area=[_far[b] for b in range(n)]

def grade(recs):
    al=[{"block_id":b,"bay_id":recs[b]["bay_id"],"orient_idx":recs[b]["orient_idx"],
         "x":recs[b]["x"],"y":recs[b]["y"],"entry_time":recs[b]["entry_time"],
         "exit_time":recs[b]["exit_time"]} for b in range(n) if b in recs]
    if len(al)!=n: return None
    return check_feasibility(inst, M._build_operations(al))

# ---- A: baseline dense construction (v71); pick first feasible (mode,step) ----
t0=time.time(); recsA=None; ckA=None; MODE=None; STEP=None
for _mode,_step in [("bigleft",2),("flatbl",2),("bigleft",1),("flatbl",1),("leftbottom",2)]:
    r=M._smallright_construct(inst, 30.0, step=_step, mode=_mode)
    c=grade(r)
    print(f"    try {_mode} step{_step}: placed={len(r) if r else 0}/{n} feas={c['feasible'] if c else None}",flush=True)
    if c and c["feasible"]: recsA=r; ckA=c; MODE=_mode; STEP=_step; break
if ckA is None:
    print(f"{NAME}: no feasible baseline construction"); sys.exit()
print(f"{NAME}: A={MODE} step{STEP}  Z1={ckA['obj1']:.0f} obj={ckA['objective']:.0f}  [{time.time()-t0:.0f}s]",flush=True)
assignA={b:recsA[b]["bay_id"] for b in recsA}
enA={b:recsA[b]["entry_time"] for b in recsA}; exA={b:recsA[b]["exit_time"] for b in recsA}
bybay=defaultdict(list)
for b in assignA: bybay[assignA[b]].append(b)

# ---- Gurobi schedule per bay (fixed assignment, calibrated achievable cap, NoRel) ----
def cbar(bl):
    ev=sorted(set(enA[b] for b in bl)); best=0.0
    for t in ev: best=max(best, sum(area[b] for b in bl if enA[b]<=t<exA[b]))
    return best
def sched_bay(bl):
    C=cbar(bl); t0=min(rel[b] for b in bl); Hmax=max(due[b] for b in bl)+max(pt[b] for b in bl)
    grid=list(range(t0,Hmax+1,GS));
    if grid[-1]!=Hmax: grid.append(Hmax)
    md=gp.Model("s"); md.setParam("OutputFlag",0); md.setParam("TimeLimit",BTL); md.setParam("Threads",4)
    md.setParam("MIPGap",0.01); md.setParam("NoRelHeurTime",0.6*BTL); md.setParam("MIPFocus",1)
    s={}
    for b in bl:
        cand=[t for t in grid if t>=rel[b]] or [grid[-1]]
        for t in cand: s[b,t]=md.addVar(vtype=GRB.BINARY)
        md.addConstr(gp.quicksum(s[b,t] for t in cand)==1)
    for t in grid:
        md.addConstr(gp.quicksum(area[b]*s[b,ts] for (b,ts) in s if ts<=t<ts+pt[b])<=C)
    T={}
    for b in bl:
        comp=gp.quicksum((ts+pt[b])*s[b,ts] for (bb,ts) in s if bb==b)
        tv=md.addVar(lb=0); md.addConstr(tv>=comp-due[b]); T[b]=tv
    md.setObjective(gp.quicksum(T.values()),GRB.MINIMIZE)
    for b in bl:
        near=min((t for (bb,t) in s if bb==b),key=lambda t:abs(t-enA[b]),default=None)
        for (bb,t) in s:
            if bb==b: s[b,t].Start=1.0 if t==near else 0.0
    md.optimize()
    if md.SolCount==0: return None
    ent={}
    for b in bl:
        for (bb,t) in s:
            if bb==b and s[b,t].X>0.5: ent[b]=t;break
    return ent

t1=time.time()
gent=[0]*n; predZ1=0
for j in range(m):
    bl=bybay[j]
    if not bl: continue
    e=sched_bay(bl)
    if e is None:
        for b in bl: gent[b]=enA[b]
        continue
    for b in bl: gent[b]=e[b]
    predZ1+=sum(max(0,e[b]+pt[b]-due[b]) for b in bl)
print(f"  Gurobi schedule pred Z1={predZ1}  (vs A {ckA['obj1']:.0f})  [{time.time()-t1:.0f}s]",flush=True)

# ---- B: SAME packer, dispatch order = Gurobi schedule ----
extbay=[assignA[b] for b in range(n)]
t2=time.time()
recsB=M._smallright_construct(inst, 40.0, step=STEP, mode=MODE, ext_entry=gent, ext_bay=extbay)
ckB=grade(recsB)
if ckB and ckB["feasible"]:
    dZ1=ckA['obj1']-ckB['obj1']; do=ckA['objective']-ckB['objective']
    print(f"  B=bigleft+Gurobi-order  Z1={ckB['obj1']:.0f} obj={ckB['objective']:.0f}  "
          f"Z1delta={dZ1:+.0f}  objdelta={do:+.0f}  "
          f"{'WIN '+str(round(100*do/max(1,ckA['objective']),1))+'%' if do>0 else 'lose'}  [{time.time()-t2:.0f}s]",flush=True)
else:
    print(f"  B infeasible/incomplete",flush=True)
