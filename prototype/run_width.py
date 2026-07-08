# width-cumulative CP-SAT order (베이가 quasi-1D라 병목은 면적이 아니라 폭).
# 수요=블록 최소폭(오리엔테이션 min bbox width), 용량=베이폭*eff.  배치는 bigleft 고정.
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _smallright_construct, _build_operations, _footprint_areas, _orient_bbox
from utils import check_feasibility
from ortools.sat.python import cp_model

def _minwidth(prob):
    B=prob["blocks"]; wmin=[]
    for b in range(len(B)):
        bw=1e18
        for oi in range(len(B[b]["shape"])):
            x0,y0,x1,y1=_orient_bbox(B[b],oi)
            bw=min(bw, x1-x0)
        wmin.append(max(1,int(round(bw))))
    return wmin

def cpsat_entry(prob, dem, caps_raw, eff, big_w, tl, nw):
    B=prob["blocks"]; n=len(B); nb=len(caps_raw)
    caps=[max(1,int(round(caps_raw[j]*eff))) for j in range(nb)]
    H=int(max(b["due_date"] for b in B)+max(b["processing_time"] for b in B)+5)
    m=cp_model.CpModel()
    ent=[m.NewIntVar(int(B[b]["release_time"]),H,"e%d"%b) for b in range(n)]
    pres={}; ivb={j:[] for j in range(nb)}; demb={j:[] for j in range(nb)}
    for b in range(n):
        pt=int(B[b]["processing_time"]); pl=[]
        for j in range(nb):
            p=m.NewBoolVar(""); pres[b,j]=p; pl.append(p)
            ivb[j].append(m.NewOptionalIntervalVar(ent[b],pt,ent[b]+pt,p,""))
            demb[j].append(dem[b])
        m.AddExactlyOne(pl)
    for j in range(nb): m.AddCumulative(ivb[j],demb[j],caps[j])
    tard=[]
    for b in range(n):
        pt=int(B[b]["processing_time"]); dd=int(B[b]["due_date"])
        t=m.NewIntVar(0,H,""); m.Add(t>=ent[b]+pt-dd); tard.append(t)
    if big_w>0:
        dmax=max(1,max(dem)); dw=[int(round(dem[b]/dmax*100)) for b in range(n)]
        K=n*100*H+1
        m.Minimize(K*sum(tard)+big_w*sum(dw[b]*ent[b] for b in range(n)))
    else:
        m.Minimize(sum(tard))
    so=cp_model.CpSolver(); so.parameters.max_time_in_seconds=float(max(2.0,tl))
    so.parameters.num_search_workers=max(1,int(nw))
    st=so.Solve(m)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None
    return [int(so.Value(ent[b])) for b in range(n)]

path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
variants=sys.argv[3].split(",") if len(sys.argv)>3 else ["rank","w_rank","wbig_rank","weff85_rank"]
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path)); n=len(prob["blocks"])
wmin=_minwidth(prob); caps_w=[b["width"] for b in prob["bays"]]
NW=max(1,min(8,(os.cpu_count() or 2))); ST=max(4.0,DL*0.45)
print(f"=== {nm} (n={n}) | bigleft gate0.60 | WIDTH-cumulative order | DL={DL:.0f}s ===",flush=True)

def run(tag, ext_entry, tiebreak="rank"):
    t=time.time()
    recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank",ext_entry,tiebreak)
    dt=time.time()-t
    if not recs or len(recs)!=n:
        print(f"  {tag:<12} 실패({len(recs) if recs else 0}/{n}) ({dt:.0f}s)",flush=True); return
    ck=check_feasibility(prob,_build_operations(list(recs.values())))
    if not ck["feasible"]:
        print(f"  {tag:<12} INFEAS stage={ck['stage']} ({dt:.0f}s)",flush=True); return
    print(f"  {tag:<12} Z1={ck['obj1']:<7.0f} obj={ck['objective']:<12.0f} Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f} ({dt:.0f}s)",flush=True)

for v in variants:
    if v=="rank": run("rank", None)
    elif v=="w_rank":
        e=cpsat_entry(prob,wmin,caps_w,1.0,0,ST,NW); run("w_rank", e)
    elif v=="wbig_rank":
        e=cpsat_entry(prob,wmin,caps_w,1.0,1,ST,NW); run("wbig_rank", e)
    elif v.startswith("weff"):
        eff=int(v[4:6])/100.0
        e=cpsat_entry(prob,wmin,caps_w,eff,1,ST,NW); run(v, e)
