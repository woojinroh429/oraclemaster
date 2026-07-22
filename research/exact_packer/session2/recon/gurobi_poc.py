"""Gurobi exact-repair PoC (concurrency-capped min total tardiness) for the most
congested bay of prob_27.  Q: within the same concurrency envelope the heuristic
already achieved (Cmax = max co-present count), can EXACT entry-time scheduling beat
the heuristic's bay tardiness?  If yes -> exact bay-window repair is promising.
Oracle-free: this is a valid cumulative relaxation; a win here motivates full LBBD.
"""
import json,os,sys,time
from collections import defaultdict
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
ENG=os.path.join(SP,"v77")   # shipped engine (survives resets) just to get a heuristic solution
sys.path.insert(0,ENG); os.environ["ENGINE_DIR"]=ENG; os.environ["NICE"]="0"
import myalgorithm as M
from utils import check_feasibility
d=json.load(open(os.path.join(SP,"data/train","prob_27.json")))
B=d["blocks"]; bays=d["bays"]
sol=M.algorithm(d,15); ck=check_feasibility(d,sol)
pl={}
for tk,lst in sol["operations"].items():
    for op in lst:
        if op.get("type")=="ENTRY":
            b=op["block_id"]; pl[b]=dict(bay=op["bay_id"],en=int(tk),ex=int(tk)+B[b]["processing_time"])
bybay=defaultdict(list)
for b,v in pl.items(): bybay[v["bay"]].append(b)
# pick most-tardy bay
def bayZ1(j): return sum(max(0,pl[b]["ex"]-B[b]["due_date"]) for b in bybay[j])
J=max(bybay, key=bayZ1)
bl=bybay[J]
rt={b:B[b]["release_time"] for b in bl}; pt={b:B[b]["processing_time"] for b in bl}; due={b:B[b]["due_date"] for b in bl}
heur_tard=bayZ1(J)
# heuristic concurrency envelope
Tmax=max(pl[b]["ex"] for b in bl)+2
def present_count(sched, t):
    return sum(1 for b in bl if sched[b]<=t<sched[b]+pt[b])
heur_sched={b:pl[b]["en"] for b in bl}
Cmax=max(present_count(heur_sched,t) for t in range(0,Tmax))
print(f"bay{J}: {len(bl)}blk  heur_bay_Z1={heur_tard}  Cmax(heur concurrency)={Cmax}  Tmax={Tmax}",flush=True)

import gurobipy as gp
from gurobipy import GRB
m=gp.Model("repair"); m.setParam("OutputFlag",0); m.setParam("TimeLimit",120); m.setParam("MIPGap",0.0)
T=list(range(0,Tmax))
z={}   # z[b,t]=start block b at t
for b in bl:
    for t in range(rt[b],Tmax):
        z[b,t]=m.addVar(vtype=GRB.BINARY,name=f"z_{b}_{t}")
for b in bl:
    m.addConstr(gp.quicksum(z[b,t] for t in range(rt[b],Tmax))==1)
# present[b,t] expression
def present(b,t):
    lo=max(rt[b], t-pt[b]+1)
    return gp.quicksum(z[b,tp] for tp in range(lo,min(t,Tmax-1)+1) if (b,tp) in z)
# concurrency cap
for t in T:
    m.addConstr(gp.quicksum(present(b,t) for b in bl) <= Cmax)
# tardiness
tard={}
for b in bl:
    start=gp.quicksum(t*z[b,t] for t in range(rt[b],Tmax))
    tv=m.addVar(lb=0.0,name=f"tard_{b}")
    m.addConstr(tv >= start + pt[b] - due[b])
    tard[b]=tv
m.setObjective(gp.quicksum(tard[b] for b in bl), GRB.MINIMIZE)
t0=time.time(); m.optimize()
print(f"GUROBI status={m.status} exact_bay_Z1={m.objVal:.0f}  vs heur={heur_tard}  [{time.time()-t0:.0f}s]",flush=True)
gain=100*(heur_tard-m.objVal)/max(1,heur_tard)
print(f"=> concurrency-capped exact scheduling: {'-' if gain>=0 else '+'}{abs(gain):.0f}%  ({'ROOM to improve' if gain>1 else 'no reorder room'})",flush=True)

# ---- LBBD: iterate master(Gurobi) + packability cuts until the schedule is packable ----
import ogc_fast
def pack_and_cut(zsol):
    """Pack the master schedule in this bay (entry order); if a block can't be seated,
    return a no-good cut set (the co-present blocks at that entry) so Gurobi forbids it.
    Returns (fully_packable, achievable_tard, list_of_cut_sets)."""
    gstart={b:int(round(sum(t*zsol[b,t] for t in range(rt[b],Tmax)))) for b in bl}
    E=M._ogc_fast_engine(d); E.clear_all()
    order=sorted(bl, key=lambda b:(gstart[b],due[b]))
    seated={}; cuts=[]; ach=0; allplaced=True
    for b in order:
        en0=gstart[b]
        # realize: place at Gurobi entry OR the earliest feasible time after it (delays -> real tardiness)
        ets=list(range(en0, Tmax+40))
        res=E.find_best_placement(b,[J],ets)
        if res[0]:
            _,bay,oi,x,y,e2,x2=res; E.add(int(bay),b,int(oi),float(x),float(y),int(e2),int(x2))
            seated[b]=int(x2); ach+=max(0,int(x2)-due[b])
            if int(e2)>en0:  # had to delay -> the co-present set at en0 was too tight
                S=[c for c in seated if c!=b and gstart[c]<=en0<gstart[c]+pt[c]]+[b]
                if len(S)>=2: cuts.append((en0,S)); allplaced=False
        else:
            allplaced=False
    return allplaced, ach, cuts

best_valid=None
for it in range(12):
    m.optimize()
    zsol={(b,t):z[b,t].X for (b,t) in z}
    ok, ach, cuts = pack_and_cut(zsol)
    print(f"  LBBD iter{it}: master={m.objVal:.0f} packable={ok} achievable={ach} cuts={len(cuts)}",flush=True)
    if ok:
        best_valid=m.objVal; break
    # add no-good cuts: forbid each unpackable co-present set at its time
    for (en,S) in cuts:
        m.addConstr(gp.quicksum(present(b,en) for b in S) <= len(S)-1)
res = best_valid if best_valid is not None else ach
print(f"LBBD result: valid_bay_Z1={res:.0f}  vs heur={heur_tard}  ({'-' if heur_tard>=res else '+'}{abs(100*(heur_tard-res)/max(1,heur_tard)):.0f}%)",flush=True)
print("ALLDONE",flush=True)
