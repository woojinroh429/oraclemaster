"""Fast capf sweep: for each area-capacity factor, solve the master, then cranepack-count
how many assigned blocks actually fit per bay (entry=release). The capf whose assignment
is ~fully realisable (fit≈n) gives a CLEAN achievable obj to compare vs v71 (~92450)."""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"cc"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
import cranepack as CP
from ortools.sat.python import cp_model
from collections import defaultdict

def find(nm):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
STEP=int(sys.argv[2]) if len(sys.argv)>2 else 6
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
w=inst["weights"]; W2=w["w2"]; W3=w["w3"]
def obb(b,o): return M._orient_bbox(B[b],o)
area=[int(round(min((obb(b,o)[2]-obb(b,o)[0])*(obb(b,o)[3]-obb(b,o)[1]) for o in range(len(B[b]["shape"]))))) for b in range(n)]
cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]
due=[B[b]["due_date"] for b in range(n)]; mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
SC=1000; avg=sum(cap)/m; U=[int(round(SC*avg/cap[j])) for j in range(m)]

def solve_master(capf, tl=8):
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
    load_v=[sum(B[b]["workload"] for b in range(n) if ext[b]==j) for j in range(m)]
    z2=max(abs(U[j]*load_v[j]-U[k]*load_v[k]) for j in range(m) for k in range(m) if j!=k)/SC
    z3=sum(mxp[b]-B[b]["bay_preferences"][ext[b]] for b in range(n))
    return ext, W2*math.floor(z2)+W3*z3, math.floor(z2), z3

_olc={}
def orient_layers(bid,o):
    k=(bid,o)
    if k not in _olc:
        _olc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64))
                 for L in M.Block(block_id=bid,block_data=B[bid],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[k]

def fit_count(ext, TL=1.5):
    tot=0
    per=[]
    for j in range(m):
        grp=[b for b in range(n) if ext[b]==j]
        if not grp: per.append((j,0,0)); continue
        W=bays[j]["width"]; H=bays[j]["height"]; blocks_in=[]
        for bid in grp:
            ols=[orient_layers(bid,o) for o in range(len(B[bid]["shape"]))]
            obbs=[tuple(float(v) for v in obb(bid,o)) for o in range(len(B[bid]["shape"]))]
            blocks_in.append((ols,obbs,[(int(rel[bid]),int(rel[bid]+pt[bid]))]))
        res=CP.pack(blocks_in,float(W),float(H),STEP,TL,seed=12345,warm=None)
        tot+=res[0]; per.append((j,len(grp),res[0]))
    return tot,per

CFS=sys.argv[3] if len(sys.argv)>3 else "1.0"   # comma list: none,1.0,0.9
TLB=float(sys.argv[4]) if len(sys.argv)>4 else 1.0
print(f"{NAME}: n={n} m={m}  v71~92450(prob_20)/~73400(prob_13)  step{STEP}")
for tok in CFS.split(","):
    cf=None if tok=="none" else float(tok)
    r=solve_master(cf)
    if r is None: print(f"  capf={tok}: master fail"); continue
    ext,obj,z2,z3=r
    t0=time.time(); fit,per=fit_count(ext,TL=TLB); dt=time.time()-t0
    detail=" ".join(f"b{j}:{f}/{g}" for j,g,f in per)
    print(f"  capf={tok:5s} OBJ={obj:6.0f} (Z2f={z2} Z3={z3})  cranepack fit={fit}/{n}  spill={n-fit}  [{detail}] [{dt:.1f}s]",flush=True)
