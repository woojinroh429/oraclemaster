# CP-SAT order 재정식화 실험. 배치는 실제 bigleft(gate0.60) 고정, 순서만 바꿈.
# 변형:
#  rank      : 기존 rank key (baseline, prob_38=2359)
#  c_due     : cpsat entry, tiebreak=due (=구 버전, 초반 wave가 EDD화)
#  c_rank    : cpsat entry, tiebreak=rank (동시입장 내 big-first 복원)
#  big_rank  : 사전식목적(1차 tard, 2차 Σarea*entry=큰블록 먼저), tiebreak=rank
#  effX_rank : eff 낮춰 더 순차적인 스케줄, tiebreak=rank
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _smallright_construct, _build_operations, _footprint_areas
from utils import check_feasibility
from ortools.sat.python import cp_model

def cpsat_entry(prob, areas, bay_caps, eff, big_w, tl, nw):
    """area-cumulative schedule.  big_w=0 -> pure tardiness. big_w>0 -> lexicographic
    (K*tardiness + big_w-scaled Sum area_i*entry_i): among min-tardiness schedules,
    pull large-area blocks to enter earliest.  Returns entry list or None."""
    B=prob["blocks"]; n=len(B); nb=len(bay_caps)
    caps=[max(1,int(round(bay_caps[j]*eff))) for j in range(nb)]
    H=int(max(b["due_date"] for b in B)+max(b["processing_time"] for b in B)+5)
    m=cp_model.CpModel()
    ent=[m.NewIntVar(int(B[b]["release_time"]),H,"e%d"%b) for b in range(n)]
    pres={}; ivb={j:[] for j in range(nb)}; demb={j:[] for j in range(nb)}
    for b in range(n):
        pt=int(B[b]["processing_time"]); pl=[]
        for j in range(nb):
            p=m.NewBoolVar("p%d_%d"%(b,j)); pres[b,j]=p; pl.append(p)
            ivb[j].append(m.NewOptionalIntervalVar(ent[b],pt,ent[b]+pt,p,""))
            demb[j].append(areas[b])
        m.AddExactlyOne(pl)
    for j in range(nb): m.AddCumulative(ivb[j],demb[j],caps[j])
    tard=[]
    for b in range(n):
        pt=int(B[b]["processing_time"]); dd=int(B[b]["due_date"])
        t=m.NewIntVar(0,H,"t%d"%b); m.Add(t>=ent[b]+pt-dd); tard.append(t)
    if big_w>0:
        amax=max(1,max(areas))
        aw=[int(round(areas[b]/amax*100)) for b in range(n)]   # 0..100
        # K makes tardiness strictly dominate: max Sum(aw*ent) < K
        K=n*100*H + 1
        m.Minimize(K*sum(tard) + big_w*sum(aw[b]*ent[b] for b in range(n)))
    else:
        m.Minimize(sum(tard))
    so=cp_model.CpSolver(); so.parameters.max_time_in_seconds=float(max(2.0,tl))
    so.parameters.num_search_workers=max(1,int(nw))
    st=so.Solve(m)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None
    return [int(so.Value(ent[b])) for b in range(n)]

path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
variants=sys.argv[3].split(",") if len(sys.argv)>3 else ["rank","c_rank","big_rank","eff50_rank"]
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path)); n=len(prob["blocks"])
areas,bay_caps,SC=_footprint_areas(prob)
NW=max(1,min(8,(os.cpu_count() or 2))); ST=max(4.0,DL*0.45)
print(f"=== {nm} (n={n}) | bigleft gate0.60 | CP-SAT order 재정식화 | DL={DL:.0f}s ===",flush=True)

def run(tag, ext_entry, tiebreak):
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
    if v=="rank":
        run("rank", None, "rank")
    elif v=="c_due":
        e=cpsat_entry(prob,areas,bay_caps,0.63,0,ST,NW); run("c_due", e, "due")
    elif v=="c_rank":
        e=cpsat_entry(prob,areas,bay_caps,0.63,0,ST,NW); run("c_rank", e, "rank")
    elif v=="big_rank":
        e=cpsat_entry(prob,areas,bay_caps,0.63,1,ST,NW); run("big_rank", e, "rank")
    elif v.startswith("eff"):
        eff=int(v[3:5])/100.0
        e=cpsat_entry(prob,areas,bay_caps,eff,1,ST,NW); run(v, e, "rank")
