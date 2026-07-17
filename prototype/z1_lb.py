"""Rigorous lower bounds on Z1 (total tardiness) via relaxations.
opt(relaxation) <= opt(real) <= v61_achieved, so these are valid LBs.
 (A) trivial per-block floor: sum max(0, release+proc-due)  [no contention]
 (B) crane-RELAXED cumulative: pool all bays into one capacity-K resource
     (K=sum bay areas), each block demands its footprint area for proc time,
     release/due kept. Ignoring crane+2D+bay-identity is a valid relaxation ->
     valid LB. Solve with CP-SAT; report solver's proven bound.
"""
import os,sys,json,time
os.environ.setdefault("ENGINE_DIR","."); sys.path.insert(0,".")
import myalgorithm as M
from ortools.sat.python import cp_model

def footprint_area(bd):
    # polygon area of orient-0 layer union proxy: use bbox area (over-est -> demand
    # higher -> LB not smaller; but for a VALID lb we under-est, so use true poly area)
    L0 = bd["shape"][0]["layers"]
    # area of bottom layer polygon (projected footprint proxy)
    def parea(pts):
        a=0.0; n=len(pts)
        for i in range(n):
            x1,y1=pts[i]; x2,y2=pts[(i+1)%n]; a+=x1*y2-x2*y1
        return abs(a)*0.5
    return max(parea(L) for L in L0) if L0 else 1.0

def trivial_lb(inst):
    s=0
    for b in inst["blocks"]:
        s+=max(0, b["release_time"]+b["processing_time"]-b["due_date"])
    return s

def cumulative_lb(inst, tl=30):
    B=inst["blocks"]; n=len(B)
    K=int(sum(bay["width"]*bay["height"] for bay in inst["bays"]))
    dem=[max(1,int(round(footprint_area(B[i])))) for i in range(n)]
    H=int(max(b["due_date"]+b["processing_time"] for b in B))+max(b["processing_time"] for b in B)
    m=cp_model.CpModel()
    starts=[]; ends=[]; ivs=[]; tard=[]
    for i in range(n):
        r=int(B[i]["release_time"]); p=int(B[i]["processing_time"]); d=int(B[i]["due_date"])
        st=m.NewIntVar(r,H,f"s{i}"); en=m.NewIntVar(r+p,H+p,f"e{i}")
        iv=m.NewIntervalVar(st,p,en,f"iv{i}")
        starts.append(st); ends.append(en); ivs.append(iv)
        t=m.NewIntVar(0,H,f"t{i}"); m.Add(t>=en-d); tard.append(t)
    m.AddCumulative(ivs,dem,K)
    m.Minimize(sum(tard))
    sv=cp_model.CpSolver(); sv.parameters.max_time_in_seconds=tl; sv.parameters.num_search_workers=4
    r=sv.Solve(m)
    return sv.BestObjectiveBound(), sv.ObjectiveValue() if r in (cp_model.OPTIMAL,cp_model.FEASIBLE) else None, K, sum(dem)

# v61 achieved Z1 (obj1) from validation
v61z1={"prob_34":44,"prob_28":102,"prob_38":2359,"prob_35":60,"prob_27":1628}
for p in sys.argv[1:]:
    inst=json.load(open(p)); nm=os.path.basename(p).replace(".json","")
    tlb=trivial_lb(inst)
    t0=time.time(); bnd,best,K,totdem=cumulative_lb(inst,25); dt=time.time()-t0
    print(f"{nm}: v61_Z1={v61z1.get(nm,'?')} | trivialLB={tlb} | cumulLB(bound)={bnd:.0f} best={best} "
          f"| K={K} totalAreaDemand={totdem} peak_density={totdem}/{K} ({dt:.0f}s)",flush=True)
print("ZLBDONE")
