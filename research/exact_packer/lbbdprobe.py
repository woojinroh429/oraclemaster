"""LBBD headroom probe. Solve the assignment MASTER (min w2*Z2 + w3*Z3) with THREE
capacity regimes and report the objective + realisability:
  (A) NO capacity      -> absolute assignment lower bound (ignores crane feasibility)
  (B) area capacity    -> what _exact_reassign's relaxation sees (capf=1.0)
  (C) area x capf sweep-> tightened, like Benders
Then, for the NO-capacity assignment, REALISE each bay with cranepack (max-count) and
report how many blocks actually fit -> tells us how much of the LB is crane-realisable.
If LB << v71 (~92450) AND cranepack realises most of it, the assignment lever is real."""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"cc"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
import cranepack as CP
from ortools.sat.python import cp_model
from collections import defaultdict

def find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
w=inst["weights"]; W2=w["w2"]; W3=w["w3"]
area=[int(round(min((M._orient_bbox(B[b],o)[2]-M._orient_bbox(B[b],o)[0])*
                     (M._orient_bbox(B[b],o)[3]-M._orient_bbox(B[b],o)[1])
                     for o in range(len(B[b]["shape"]))))) for b in range(n)]
cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]
mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
SC=1000; avg=sum(cap)/m
U=[int(round(SC*avg/cap[j])) for j in range(m)]

def solve_master(capf, tl=10):
    mdl=cp_model.CpModel()
    x=[[mdl.NewBoolVar(f"x{b}_{j}") for j in range(m)] for b in range(n)]
    for b in range(n): mdl.Add(sum(x[b])==1)
    load=[mdl.NewIntVar(0,10**7,f"l{j}") for j in range(m)]
    for j in range(m): mdl.Add(load[j]==sum(x[b][j]*int(B[b]["workload"]) for b in range(n)))
    Mv=mdl.NewIntVar(0,10**12,"M")
    for j in range(m):
        for k in range(m):
            if j!=k: mdl.Add(Mv>=U[j]*load[j]-U[k]*load[k])
    if capf is not None:
        for j in range(m):
            for t in sorted(set(rel)):
                present=[b for b in range(n) if rel[b]<=t<rel[b]+pt[b]]
                if present: mdl.Add(sum(x[b][j]*area[b] for b in present)<=int(cap[j]*capf))
    Z3=sum(x[b][j]*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    mdl.Minimize(W2*Mv+W3*SC*Z3)
    slv=cp_model.CpSolver(); slv.parameters.max_time_in_seconds=tl; slv.parameters.num_search_workers=4
    st=slv.Solve(mdl)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None
    ext=[next(j for j in range(m) if slv.Value(x[b][j])==1) for b in range(n)]
    # true obj components
    load_v=[sum(B[b]["workload"] for b in range(n) if ext[b]==j) for j in range(m)]
    z2=max(abs(U[j]*load_v[j]-U[k]*load_v[k]) for j in range(m) for k in range(m) if j!=k)/SC
    z3=sum(mxp[b]-B[b]["bay_preferences"][ext[b]] for b in range(n))
    obj=W2*math.floor(z2)+W3*z3
    return ext,obj,math.floor(z2),z3,slv.StatusName(st),0.0

def orient_layers(bid,o):
    return [np.ascontiguousarray(np.asarray(L,dtype=np.float64))
            for L in M.Block(block_id=bid,block_data=B[bid],x=0,y=0,orient_idx=o).layers_at_pos()]

def cranepack_realise(ext, STEP=6, TL=1.0):
    """For each bay, cranepack-place its assigned blocks (entry=release). Return #fit per bay."""
    fit=0; spilled=0
    for j in range(m):
        grp=[b for b in range(n) if ext[b]==j]
        if not grp: continue
        W=bays[j]["width"]; H=bays[j]["height"]; blocks_in=[]
        for bid in grp:
            ols=[orient_layers(bid,o) for o in range(len(B[bid]["shape"]))]
            obbs=[tuple(float(v) for v in M._orient_bbox(B[bid],o)) for o in range(len(B[bid]["shape"]))]
            en=rel[bid]; ex=en+pt[bid]; blocks_in.append((ols,obbs,[(int(en),int(ex))]))
        res=CP.pack(blocks_in,float(W),float(H),STEP,TL,seed=12345,warm=None)
        best=res[0]; fit+=best; spilled+=len(grp)-best
    return fit,spilled

print(f"{NAME}: n={n} m={m}  w2={W2} w3={W3}  (v71 ~92450 for prob_20)")
for label,capf in [("NO-cap (LB)",None),("area capf=1.0",1.0),("area capf=0.85",0.85)]:
    t0=time.time(); r=solve_master(capf,tl=10)
    if r is None: print(f"  {label}: infeasible/timeout"); continue
    ext,obj,z2,z3,stt,bnd=r
    line=f"  {label:16s}: OBJ={obj:.0f}  Z2f={z2} (w2Z2={W2*z2}) Z3={z3} (w3Z3={W3*z3})  [{stt} {time.time()-t0:.1f}s]"
    if capf is None:
        fit,spill=cranepack_realise(ext)
        line+=f"\n      cranepack realise: fit={fit}/{n} spill={spill} (spill blocks must move -> real obj higher)"
    print(line)
