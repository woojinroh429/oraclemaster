# 시간창 Ruin + CP-SAT(windowed) exact Recreate  프로토타입.
# 한 프로세스=한 인스턴스 (실 알고리즘과 동일, 상태오염 없음).
# 단계: baseline(rank+bigleft) -> 혼잡 시간창 식별 -> ruin(창 블록 제거, 나머지 고정)
#       -> CP-SAT로 창 블록 재스케줄(고정블록=배경수요) -> 엔진으로 잔여공간에 realize
#       -> 공식 check_feasibility 검증 -> baseline과 best-of. 절대 무회귀.
import os, sys, json, time, argparse
import numpy as np
sys.path.insert(0, os.environ.get("ENGINE_DIR","../sv34"))
import myalgorithm as M
from myalgorithm import (_smallright_construct, _build_operations, _ogc_fast_engine,
                         _footprint_areas, _orient_bbox)
from utils import check_feasibility

def objize(inst, recs):
    ck = check_feasibility(inst, _build_operations([recs[b] for b in range(len(recs))]))
    return ck

def baseline(inst, DL, STEP):
    recs = _smallright_construct(inst, DL, 0.60, STEP, "bigleft", "rank", tiebreak="due")
    if not recs or len(recs)!=len(inst["blocks"]): return None,None
    ck = objize(inst, recs)
    return recs, ck

def find_window(inst, recs, areas, target=30):
    """혼잡 시간창을 |W|<=target 로 제한. 지각밀도(각 시각에 존재하는 '지각블록' 수) 최대
    지점 t* 를 잡고, 창을 t* 중심으로 |W|가 target에 닿을 때까지 확장. 반환 (t1,t2,W)."""
    B=inst["blocks"]; n=len(B)
    tard_of=[max(0,recs[b]["exit_time"]-B[b]["due_date"]) for b in range(n)]
    # 각 event 시각의 '지각기여 블록' 존재 수로 피크 t* 찾기
    ev=sorted(set([recs[b]["entry_time"] for b in range(n)]+[recs[b]["exit_time"] for b in range(n)]))
    def present(t): return [b for b in range(n) if recs[b]["entry_time"]<=t<recs[b]["exit_time"]]
    best=(-1.0,ev[0])
    for t in ev:
        s=sum(tard_of[b]>0 for b in present(t))
        if s>best[0]: best=(s,t)
    tstar=best[1]
    # tstar 중심으로 창 확장 (좌우 event 경계로 넓히며 |W| 제한)
    lo=hi=ev.index(tstar) if tstar in ev else 0
    def Wset(t1,t2): return set(b for b in range(n) if recs[b]["entry_time"]<t2 and recs[b]["exit_time"]>t1)
    t1=t2=tstar
    while True:
        cand=[]
        if lo>0: cand.append(("lo",ev[lo-1],t2))
        if hi<len(ev)-1: cand.append(("hi",t1,ev[hi+1]))
        if not cand: break
        # 더 작게 늘어나는 쪽 선택
        pick=min(cand,key=lambda c:len(Wset(c[1],c[2])))
        if len(Wset(pick[1],pick[2]))>target: break
        if pick[0]=="lo": lo-=1; t1=pick[1]
        else: hi+=1; t2=pick[2]
        if lo==0 and hi==len(ev)-1: break
    return t1,t2,Wset(t1,t2)

def recreate(inst, recs, W, order_W, areas, force_delay=None):
    """F(창밖)=고정, W=order_W 순서로 엔진 잔여공간에 재배치. force_delay[b]=최소 entry.
    반환 새 recs dict 또는 None."""
    n=len(inst["blocks"]); B=inst["blocks"]; n_bays=len(inst["bays"]); bay_list=list(range(n_bays))
    E=_ogc_fast_engine(inst); E.clear_all()
    F=[b for b in range(n) if b not in W]
    for b in F:
        r=recs[b]; E.add(r["bay_id"],b,r["orient_idx"],float(r["x"]),float(r["y"]),
                         int(r["entry_time"]),int(r["exit_time"]))
    new={b:dict(recs[b]) for b in F}
    placed_ex=[recs[b]["exit_time"] for b in F]
    for b in order_W:
        rt=int(B[b]["release_time"])
        lo=rt if force_delay is None else max(rt,int(force_delay.get(b,rt)))
        base={lo}|{int(e) for e in placed_ex if e>=lo}
        res=E.find_best_placement(b,bay_list,sorted(base))
        if not res or not res[0]:
            et=lo; ok=False; g=0
            while not ok and g<400:
                g+=1; res=E.find_best_placement(b,bay_list,[et])
                if res and res[0]: ok=True
                else: et+=1
            if not ok: return None
        _,bj,oi,x,y,en,ex=res
        E.add(int(bj),b,int(oi),float(x),float(y),int(en),int(ex))
        new[b]={"block_id":b,"bay_id":int(bj),"x":int(x),"y":int(y),
                "orient_idx":int(oi),"entry_time":int(en),"exit_time":int(ex)}
        placed_ex.append(ex)
    if len(new)!=n: return None
    return new

def recreate_regret(inst, recs, W, areas, k=2):
    """Regret-k recreate: F고정, W를 매 스텝 '후회(regret)=차선-최선 tardiness' 최대 블록부터
    최선 위치에 삽입 (greedy 고정순서 대신 동적 난이도순). 반환 새 recs 또는 None."""
    n=len(inst["blocks"]); B=inst["blocks"]; n_bays=len(inst["bays"]); bay_list=list(range(n_bays))
    E=_ogc_fast_engine(inst); E.clear_all()
    F=[b for b in range(n) if b not in W]
    for b in F:
        r=recs[b]; E.add(r["bay_id"],b,r["orient_idx"],float(r["x"]),float(r["y"]),
                         int(r["entry_time"]),int(r["exit_time"]))
    new={b:dict(recs[b]) for b in F}
    placed_ex=[recs[b]["exit_time"] for b in F]
    remaining=set(W)
    def best_per_bay(b):
        rt=int(B[b]["release_time"]); dd=B[b]["due_date"]
        base=sorted({rt}|{int(e) for e in placed_ex if e>=rt})
        costs=[]
        for j in bay_list:
            res=E.find_best_placement(b,[j],base)
            if res and res[0]:
                _,bj,oi,x,y,en,ex=res; costs.append((max(0,ex-dd),ex,(bj,oi,x,y,en,ex)))
        costs.sort()
        return costs
    while remaining:
        best_pick=None  # (regret, -tard, b, placement)
        for b in list(remaining):
            costs=best_per_bay(b)
            if not costs:
                continue
            t1=costs[0][0]; t2=costs[k-1][0] if len(costs)>=k else costs[-1][0]
            regret=t2-t1
            keyv=(regret, -t1)
            if best_pick is None or keyv>best_pick[0]:
                best_pick=(keyv,b,costs[0][2])
        if best_pick is None:
            return None
        _,b,pl=best_pick; bj,oi,x,y,en,ex=pl
        E.add(int(bj),b,int(oi),float(x),float(y),int(en),int(ex))
        new[b]={"block_id":b,"bay_id":int(bj),"x":int(x),"y":int(y),
                "orient_idx":int(oi),"entry_time":int(en),"exit_time":int(ex)}
        placed_ex.append(ex); remaining.discard(b)
    return new if len(new)==n else None

def cpsat_window(inst, recs, W, areas, bay_caps, eff, tl):
    """W 블록만 재스케줄(베이=baseline 고정). F=고정 배경수요. W 지각합 최소화 -> entry[b]."""
    try: from ortools.sat.python import cp_model
    except Exception: return None
    B=inst["blocks"]; n=len(B); nb=len(bay_caps)
    caps=[max(1,int(round(bay_caps[j]*eff))) for j in range(nb)]
    H=int(max(bd["due_date"] for bd in B)+max(bd["processing_time"] for bd in B)+5)
    m=cp_model.CpModel()
    Wl=sorted(W); entry={}; ivb={j:[] for j in range(nb)}; demb={j:[] for j in range(nb)}
    for b in Wl:
        j=recs[b]["bay_id"]; pt=int(B[b]["processing_time"])
        e=m.NewIntVar(int(B[b]["release_time"]),H,"e%d"%b); entry[b]=e
        ivb[j].append(m.NewIntervalVar(e,pt,e+pt,"iv%d"%b)); demb[j].append(int(areas[b]))
    # F 고정 배경수요
    for b in range(n):
        if b in W: continue
        j=recs[b]["bay_id"]; en=int(recs[b]["entry_time"]); ex=int(recs[b]["exit_time"])
        if ex<=en: continue
        ivb[j].append(m.NewIntervalVar(en,ex-en,ex,"f%d"%b)); demb[j].append(int(areas[b]))
    for j in range(nb):
        if ivb[j]: m.AddCumulative(ivb[j],demb[j],caps[j])
    _ = caps  # eff auto-relax handled by caller
    tard=[]
    for b in Wl:
        pt=int(B[b]["processing_time"]); dd=int(B[b]["due_date"])
        t=m.NewIntVar(0,H,"t%d"%b); m.Add(t>=entry[b]+pt-dd); tard.append(t)
    m.Minimize(sum(tard))
    s=cp_model.CpSolver(); s.parameters.max_time_in_seconds=tl
    s.parameters.num_search_workers=max(1,min(4,os.cpu_count() or 2))
    st=s.Solve(m)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None
    return {b:int(s.Value(entry[b])) for b in Wl}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("inst"); ap.add_argument("--dl",type=float,default=15.0)
    ap.add_argument("--step",type=int,default=1); ap.add_argument("--target",type=int,default=30); a=ap.parse_args()
    inst=json.load(open(a.inst)); name=os.path.basename(a.inst).replace(".json","")
    B=inst["blocks"]; n=len(B)
    areas,bay_caps,_=_footprint_areas(inst)
    recs,ck=baseline(inst,a.dl,a.step)
    if recs is None: print(f"{name}: baseline FAIL"); return
    print(f"{name}: n={n} baseline feasible={ck['feasible']} Z1={ck['obj1']:.0f} obj={ck['objective']:.0f}")
    t1,t2,W=find_window(inst,recs,areas,target=a.target)
    tardy=[b for b in range(n) if recs[b]["exit_time"]>B[b]["due_date"]]
    tard_in_W=sum(max(0,recs[b]["exit_time"]-B[b]["due_date"]) for b in W)
    print(f"  window=[{t1},{t2}] |W|={len(W)} tardy_blocks={len(tardy)} tardiness_in_W={tard_in_W:.0f}/{ck['obj1']:.0f}")
    # 창 블록 베이 분포
    from collections import Counter
    print(f"  W bays: {dict(Counter(recs[b]['bay_id'] for b in W))}")

    # dispatch rank key (baseline 순서 재현용)
    due=np.array([b["due_date"] for b in B],float); rel=np.array([b["release_time"] for b in B],float)
    ar=np.array([areas[b] for b in range(n)])
    def rof(v,rev):
        o=np.argsort(-v if rev else v); r=np.zeros(n); r[o]=np.arange(n)/max(1,n-1); return r
    rk=rof(due,False)+rof(ar,True)
    order_rank=sorted(W,key=lambda b:(rk[b],due[b]))

    # (a) CONTROL: F고정 + W를 baseline rank순 재배치 (고정 handicap 측정)
    rc=recreate(inst,recs,W,order_rank,areas)
    if rc is not None:
        ckc=objize(inst,rc); print(f"  [control  ] feasible={ckc['feasible']} Z1={ckc['obj1']:.0f} obj={ckc['objective']:.0f}")
    else:
        print("  [control  ] recreate FAIL")

    # (a2) REGRET-2 recreate (greedy를 이기는지)
    rg=recreate_regret(inst,recs,W,areas,k=2)
    if rg is not None:
        ckg=objize(inst,rg); print(f"  [regret-2 ] feasible={ckg['feasible']} Z1={ckg['obj1']:.0f} obj={ckg['objective']:.0f}")
    else:
        print("  [regret-2 ] recreate FAIL")

    # (b) CP-SAT window recreate
    t0=time.time(); sched=None; used_eff=None
    for eff in (0.72,0.9,1.1,1.4,1.8):
        sched=cpsat_window(inst,recs,W,areas,bay_caps,eff,min(15.0,a.dl))
        if sched is not None: used_eff=eff; break
    if sched is None:
        print("  [cpsat    ] CP-SAT FAIL (all eff infeasible)"); return
    print(f"  [cpsat    ] solved at eff={used_eff}")
    order_cp=sorted(W,key=lambda b:(sched[b],rk[b]))
    rcp=recreate(inst,recs,W,order_cp,areas,force_delay=sched)
    if rcp is None:
        print(f"  [cpsat    ] recreate FAIL ({time.time()-t0:.1f}s)"); return
    ckp=objize(inst,rcp)
    d1=100*(ck['obj1']-ckp['obj1'])/max(1,ck['obj1']); do=100*(ck['objective']-ckp['objective'])/max(1,ck['objective'])
    print(f"  [cpsat    ] feasible={ckp['feasible']} Z1={ckp['obj1']:.0f} obj={ckp['objective']:.0f}  dZ1={d1:+.2f}% dobj={do:+.2f}% ({time.time()-t0:.1f}s)")
    # best-of: baseline vs cpsat (control은 참고용)
    best=min([(ck['objective'],'baseline'),(ckp['objective'] if ckp['feasible'] else 1e18,'cpsat')])
    print(f"  => best-of: {best[1]} obj={min(ck['objective'], ckp['objective'] if ckp['feasible'] else 1e18):.0f}")

if __name__=="__main__": main()
