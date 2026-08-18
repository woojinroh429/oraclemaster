# rank 순서는 유지, 베이 배정만 CP-SAT로 co-optimize (rank가 안 건드리는 자유도).
# area 또는 width cumulative로 (tard, bay, entry) 풀고 bay만 강제. 배치는 bigleft.
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _smallright_construct, _build_operations, _footprint_areas, _orient_bbox
from utils import check_feasibility
from ortools.sat.python import cp_model

def _minwidth(prob):
    B=prob["blocks"]; out=[]
    for b in range(len(B)):
        bw=1e18
        for oi in range(len(B[b]["shape"])):
            x0,y0,x1,y1=_orient_bbox(B[b],oi); bw=min(bw,x1-x0)
        out.append(max(1,int(round(bw))))
    return out

def cpsat_sched(prob, dem, caps_raw, eff, tl, nw):
    B=prob["blocks"]; n=len(B); nb=len(caps_raw)
    caps=[max(1,int(round(caps_raw[j]*eff))) for j in range(nb)]
    H=int(max(b["due_date"] for b in B)+max(b["processing_time"] for b in B)+5)
    m=cp_model.CpModel()
    ent=[m.NewIntVar(int(B[b]["release_time"]),H,"") for b in range(n)]
    pres={}; ivb={j:[] for j in range(nb)}; demb={j:[] for j in range(nb)}
    for b in range(n):
        pt=int(B[b]["processing_time"]); pl=[]
        for j in range(nb):
            p=m.NewBoolVar(""); pres[b,j]=p; pl.append(p)
            ivb[j].append(m.NewOptionalIntervalVar(ent[b],pt,ent[b]+pt,p,"")); demb[j].append(dem[b])
        m.AddExactlyOne(pl)
    for j in range(nb): m.AddCumulative(ivb[j],demb[j],caps[j])
    tard=[]
    for b in range(n):
        pt=int(B[b]["processing_time"]); dd=int(B[b]["due_date"])
        t=m.NewIntVar(0,H,""); m.Add(t>=ent[b]+pt-dd); tard.append(t)
    m.Minimize(sum(tard))
    so=cp_model.CpSolver(); so.parameters.max_time_in_seconds=float(max(2.0,tl)); so.parameters.num_search_workers=max(1,int(nw))
    st=so.Solve(m)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None
    bay=[0]*n
    for b in range(n):
        for j in range(nb):
            if so.Value(pres[b,j])==1: bay[b]=j; break
    return bay,[int(so.Value(ent[b])) for b in range(n)]

path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
variants=sys.argv[3].split(",") if len(sys.argv)>3 else ["rank","abay","wbay"]
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path)); n=len(prob["blocks"])
areas,acap,SC=_footprint_areas(prob); wmin=_minwidth(prob); wcap=[b["width"] for b in prob["bays"]]
NW=max(1,min(8,(os.cpu_count() or 2))); ST=max(4.0,DL*0.45)
print(f"=== {nm} (n={n}) | bigleft gate0.60 | CP-SAT BAY 배정 (순서=rank) | DL={DL:.0f}s ===",flush=True)

def run(tag, ext_bay):
    t=time.time()
    recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank",None,"rank",ext_bay)
    dt=time.time()-t
    if not recs or len(recs)!=n:
        print(f"  {tag:<10} 실패({len(recs) if recs else 0}/{n}) ({dt:.0f}s)",flush=True); return
    ck=check_feasibility(prob,_build_operations(list(recs.values())))
    if not ck["feasible"]:
        print(f"  {tag:<10} INFEAS stage={ck['stage']} ({dt:.0f}s)",flush=True); return
    print(f"  {tag:<10} Z1={ck['obj1']:<7.0f} obj={ck['objective']:<12.0f} Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f} ({dt:.0f}s)",flush=True)

for v in variants:
    if v=="rank": run("rank", None)
    elif v=="abay":
        r=cpsat_sched(prob,areas,acap,0.63,ST,NW); run("abay(area)", r[0] if r else None)
    elif v=="wbay":
        r=cpsat_sched(prob,wmin,wcap,1.0,ST,NW); run("wbay(width)", r[0] if r else None)
