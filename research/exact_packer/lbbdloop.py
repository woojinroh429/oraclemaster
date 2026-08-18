"""cranepack-oracle LBBD loop.  Master = min w2*Z2 + w3*Z3 with a per-bay BLOCK-COUNT
cap (no area).  Subproblem = cranepack realise each bay (true crane capacity).  Tighten
the spilling bays' caps to the realised fit, re-solve, until fully realisable.  Each round
also builds a complete incumbent (spilled -> best other bay) and grader-scores it.
Reports the best grader obj vs v71 (~92450 prob_20)."""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"cc"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
from utils import check_feasibility
import cranepack as CP
from ortools.sat.python import cp_model
from collections import defaultdict

def find(nm):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
STEP=int(sys.argv[2]) if len(sys.argv)>2 else 8
ROUNDS=int(sys.argv[3]) if len(sys.argv)>3 else 6
TLB=float(sys.argv[4]) if len(sys.argv)>4 else 1.5
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
w=inst["weights"]; W2=w["w2"]; W3=w["w3"]
def obb(b,o): return M._orient_bbox(B[b],o)
rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]
due=[B[b]["due_date"] for b in range(n)]; mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
SC=1000; avg=sum(cap)/m; U=[int(round(SC*avg/cap[j])) for j in range(m)]

def solve_master(capcount, tl=8):
    mdl=cp_model.CpModel()
    x=[[mdl.NewBoolVar(f"x{b}_{j}") for j in range(m)] for b in range(n)]
    for b in range(n): mdl.Add(sum(x[b])==1)
    for j in range(m):
        if capcount[j] < n: mdl.Add(sum(x[b][j] for b in range(n)) <= capcount[j])
    load=[mdl.NewIntVar(0,10**7,f"l{j}") for j in range(m)]
    for j in range(m): mdl.Add(load[j]==sum(x[b][j]*int(B[b]["workload"]) for b in range(n)))
    Mv=mdl.NewIntVar(0,10**12,"M")
    for j in range(m):
        for k in range(m):
            if j!=k: mdl.Add(Mv>=U[j]*load[j]-U[k]*load[k])
    Z3=sum(x[b][j]*(mxp[b]-B[b]["bay_preferences"][j]) for b in range(n) for j in range(m))
    mdl.Minimize(W2*Mv+W3*SC*Z3)
    slv=cp_model.CpSolver(); slv.parameters.max_time_in_seconds=tl; slv.parameters.num_search_workers=4
    st=slv.Solve(mdl)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None
    return [next(j for j in range(m) if slv.Value(x[b][j])==1) for b in range(n)]

_olc={}
def orient_layers(bid,o):
    k=(bid,o)
    if k not in _olc:
        _olc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64))
                 for L in M.Block(block_id=bid,block_data=B[bid],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[k]

def pack_bay(grp,j,frozen=None,TL=None):
    if TL is None: TL=TLB
    if not grp: return {},[]
    W=bays[j]["width"]; H=bays[j]["height"]; blocks_in=[]; cli=[]
    for bid in grp:
        cli.append(bid)
        ols=[orient_layers(bid,o) for o in range(len(B[bid]["shape"]))]
        obbs=[tuple(float(v) for v in obb(bid,o)) for o in range(len(B[bid]["shape"]))]
        blocks_in.append((ols,obbs,[(int(rel[bid]),int(rel[bid]+pt[bid]))]))
    res=CP.pack(blocks_in,float(W),float(H),STEP,TL,seed=12345,warm=None,frozen=frozen)
    placed={}
    for (loc,o,x,y,en,ex) in res[1]: placed[cli[loc]]=(o,x,y,en,ex)
    return placed,[b for b in grp if b not in placed]

def realise(ext):
    """cranepack-realise every bay (entry=release). Return placement, per-bay (g,fit), total fit."""
    placement={}; fitper={}
    for j in range(m):
        grp=[b for b in range(n) if ext[b]==j]
        placed,unpl=pack_bay(grp,j)
        for bid,v in placed.items(): placement[bid]=(j,)+v
        fitper[j]=(len(grp),len(placed))
    return placement,fitper,len(placement)

def grade(placement):
    al=[{"block_id":bid,"bay_id":placement[bid][0],"orient_idx":placement[bid][1],"x":placement[bid][2],
         "y":placement[bid][3],"entry_time":placement[bid][4],"exit_time":placement[bid][5]} for bid in range(n)]
    ck=check_feasibility(inst,M._build_operations(al))
    return ck if ck["feasible"] else None

print(f"{NAME}: n={n} m={m} step{STEP}  (v71~92450 prob_20 / ~73400 prob_13)",flush=True)
T0=time.time()
# 1) Z3-optimal master assignment (no capacity)
ext=solve_master([n]*m, tl=8)
if ext is None: print("  master fail"); sys.exit(1)
z3a=sum(mxp[b]-B[b]["bay_preferences"][ext[b]] for b in range(n))
print(f"  master (no-cap): assign-Z3={z3a}  [{time.time()-T0:.0f}s]",flush=True)

# 2) spill cascade: realise all bays; unplaced -> next-best OTHER bay; repeat.
prefrank={b:sorted(range(m),key=lambda q:-B[b]["bay_preferences"][q]) for b in range(n)}
tried=defaultdict(set)  # bays already tried per block (avoid loops)
for b in range(n): tried[b].add(ext[b])
best_obj=float("inf")
for rd in range(ROUNDS):
    placement,fitper,fit=realise(ext)
    line=f"  rd{rd}: fit={fit}/{n}"
    if fit==n:
        ck=grade(placement)
        if ck:
            line+=f"  REALISED obj={ck['objective']:.0f} (Z1={ck['obj1']:.0f} Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f})"
            best_obj=min(best_obj,ck["objective"])
        else: line+="  (grader INFEASIBLE)"
        line+=f"  [{time.time()-T0:.0f}s]"; print(line,flush=True); break
    # reassign unplaced blocks to their next untried preferred bay
    placed_ids=set(placement); moved=0
    for b in range(n):
        if b in placed_ids: continue
        for jj in prefrank[b]:
            if jj not in tried[b]:
                ext[b]=jj; tried[b].add(jj); moved+=1; break
    z3a=sum(mxp[b]-B[b]["bay_preferences"][ext[b]] for b in range(n))
    line+=f"  spill={n-fit} reassigned={moved} newZ3={z3a}  [{time.time()-T0:.0f}s]"
    print(line,flush=True)
    if moved==0:
        print("  no reassign possible (some block exhausted all bays)"); break
print(f"  >>> BEST realised obj={best_obj:.0f}  vs v71~92450  ({'WIN -'+str(round(100*(1-best_obj/92450)))+'%' if best_obj<92450 else '-'})",flush=True)
