# ============================================================================
# OGC2026 패턴기반 set-partitioning ILP 프로토타입 (CP-SAT = Gurobi 대역).
# 목표: "기하를 미리 검증한 배치후보에 ILP를 가둔다" 가 tractable + 우리 휴리스틱을
# 이기는지 소형 인스턴스로 검증.  되면 Gurobi로 포팅.
#
# ── 추가한 제약 (= 탐색량 줄이는 트릭, 승리팀의 'BFS 높이단조'에 대응) ──────────
#  A1. 위치 이산화: 연속 (x,y) 대신 베이별 COARSE GRID 후보위치만 (폭방향 GX개, 높이 GY개).
#      -> 연속 2D 해집합을 유한 슬롯으로 제한 (정확도↓ 대신 tractable).
#  A2. 진입시각 이산화: e_i ∈ {release_i, +δ 몇 개}  (연속 시간축 제한).
#  A3. 기하+크레인을 배치후보에 BAKE-IN: 각 배치는 빈 베이에 fit 사전검증(placement_feasible),
#      공존가능성(같은베이·시간겹침 쌍)은 엔진으로 사전검증 -> 충돌쌍만 ILP 제약 y+y'<=1.
#      => ILP는 '깨끗한 조합문제'(기하식 없음) -> CP-SAT/Gurobi가 강점.
#  A4. 쌍(pairwise) 충돌만 모델; 3자+ 충돌은 최종 공식 checker 검증 후 no-good cut (Benders).
#
# 결정변수 y[ρ]∈{0,1} (배치 ρ 사용).  제약: 블록마다 Σy=1(분할), 충돌쌍 y+y'<=1.
# 목적: w1·Σtard·y + w3·Σpref·y  (+ w2·Z2 부하불균형, 옵션).
# ============================================================================
import os, sys, json, time, copy, itertools
sys.path.insert(0, os.environ.get("ENGINE_DIR","../ad"))
import myalgorithm as M
from myalgorithm import _ogc_fast_engine, _build_operations, _orient_bbox, _smallright_construct
from utils import check_feasibility
from ortools.sat.python import cp_model

def subinstance(inst, K):
    d = copy.deepcopy(inst); d["blocks"] = d["blocks"][:K]; return d

def gen_placements(inst, GX=6, GY=2, dt_list=(0,3,7), keepK=10, seed_sol=None):
    """각 블록의 배치후보 풀 생성 (A1 격자위치, A2 진입시각, A3 fit 검증).
    seed_sol: 휴리스틱 해(블록->배치).  풀에 넣어 '실행가능 패킹 최소 1개 존재' 보장
    (column-gen warm-start) -> ILP는 휴리스틱의 이웃을 exact 탐색 = 무회귀 정제."""
    B=inst["blocks"]; n=len(B); bays=inst["bays"]; nb=len(bays)
    E=_ogc_fast_engine(inst)
    by_block=[[] for _ in range(n)]
    def _mk(i,j,o,ix,iy,en):
        pt=int(B[i]["processing_time"]); dd=B[i]["due_date"]; mp=max(B[i]["bay_preferences"])
        ex=en+pt
        return dict(i=i,j=j,o=o,x=int(ix),y=int(iy),en=int(en),ex=int(ex),
                    tard=max(0,ex-dd),pref=mp-B[i]["bay_preferences"][j],wl=B[i]["workload"],seed=False)
    for i in range(n):
        rt=int(B[i]["release_time"]); pt=int(B[i]["processing_time"]); dd=B[i]["due_date"]
        mp=max(B[i]["bay_preferences"])
        cands=[]
        for j in range(nb):
            bw=bays[j]["width"]; bh=bays[j]["height"]
            for o in range(len(B[i]["shape"])):
                x0,y0,x1,y1=_orient_bbox(B[i],o); w=x1-x0; h=y1-y0
                if w>bw or h>bh: continue
                xs=[round(gx*(bw-w)/max(1,GX-1)) for gx in range(GX)] if GX>1 else [0]
                ys=[round(gy*(bh-h)/max(1,GY-1)) for gy in range(GY)] if GY>1 else [0]
                for dt in dt_list:
                    en=rt+dt; ex=en+pt
                    for gx in sorted(set(xs)):
                        for gy in sorted(set(ys)):
                            # ix,iy are lower-left of bbox origin (place_custom uses ix,iy s.t. wx=ix+x0)
                            ix=gx-x0; iy=gy-y0
                            E.clear_all()
                            if E.placement_feasible(j,i,o,float(ix),float(iy),en,ex):
                                tard=max(0,ex-dd); pref=mp-B[i]["bay_preferences"][j]
                                cands.append(dict(i=i,j=j,o=o,x=int(ix),y=int(iy),en=en,ex=ex,
                                                  tard=tard,pref=pref,wl=B[i]["workload"]))
        # keep best-K by (tard, pref) to bound pool
        cands.sort(key=lambda c:(c["tard"], c["pref"], c["en"]))
        by_block[i]=cands[:keepK]
    # A-seed: guarantee the heuristic packing exists in the pool (feasible warm-start)
    if seed_sol is not None:
        for i in range(n):
            r=seed_sol[i]
            sp=_mk(i,r["bay_id"],r["orient_idx"],r["x"],r["y"],r["entry_time"]); sp["seed"]=True
            # drop any pool dup at same slot, put seed first
            by_block[i]=[sp]+[p for p in by_block[i]
                              if not (p["j"]==sp["j"] and p["x"]==sp["x"] and p["y"]==sp["y"]
                                      and p["en"]==sp["en"] and p["o"]==sp["o"])]
    return by_block

def coexist(inst, E, a, b):
    """A3: 두 배치가 같은 베이·시간겹침일 때 공존 가능? (엔진, 양방향 근사)."""
    if a["j"]!=b["j"]: return True
    if not (a["en"]<b["ex"] and b["en"]<a["ex"]): return True  # no time overlap
    E.clear_all()
    E.add(a["j"],a["i"],a["o"],float(a["x"]),float(a["y"]),a["en"],a["ex"])
    if not E.placement_feasible(b["j"],b["i"],b["o"],float(b["x"]),float(b["y"]),b["en"],b["ex"]):
        return False
    E.clear_all()
    E.add(b["j"],b["i"],b["o"],float(b["x"]),float(b["y"]),b["en"],b["ex"])
    if not E.placement_feasible(a["j"],a["i"],a["o"],float(a["x"]),float(a["y"]),a["en"],a["ex"]):
        return False
    return True

def solve_ilp(inst, by_block, tl=30, use_z2=False):
    B=inst["blocks"]; n=len(B); w=inst["weights"]; nb=len(inst["bays"])
    E=_ogc_fast_engine(inst)
    P=[p for lst in by_block for p in lst]           # flat placement pool
    idx={id(p):k for k,p in enumerate(P)}
    # pairwise conflicts
    t0=time.time(); conflicts=[]
    for a in range(len(P)):
        for b in range(a+1,len(P)):
            if P[a]["i"]==P[b]["i"]: continue
            if not coexist(inst,E,P[a],P[b]): conflicts.append((a,b))
    tconf=time.time()-t0
    m=cp_model.CpModel()
    y=[m.NewBoolVar(f"y{k}") for k in range(len(P))]
    for i in range(n):
        m.Add(sum(y[idx[id(p)]] for p in by_block[i])==1)   # partition
    for a,b in conflicts:
        m.Add(y[a]+y[b]<=1)                                  # conflict
    obj=w["w1"]*sum(P[k]["tard"]*y[k] for k in range(len(P))) \
        + w["w3"]*sum(P[k]["pref"]*y[k] for k in range(len(P)))
    m.Minimize(obj)
    s=cp_model.CpSolver(); s.parameters.max_time_in_seconds=tl
    s.parameters.num_search_workers=4
    st=s.Solve(m)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None,None,tconf,len(P),len(conflicts)
    sol={}
    for i in range(n):
        for p in by_block[i]:
            if s.Value(y[idx[id(p)]])==1:
                sol[i]={"block_id":i,"bay_id":p["j"],"x":p["x"],"y":p["y"],
                        "orient_idx":p["o"],"entry_time":p["en"],"exit_time":p["ex"]}
    return sol, s.ObjectiveValue(), tconf, len(P), len(conflicts)

def main():
    inst=json.load(open(sys.argv[1])); K=int(sys.argv[2] if len(sys.argv)>2 else 12)
    sub=subinstance(inst,K)
    print(f"sub-instance: {K} blocks, {len(sub['bays'])} bays, weights={sub['weights']}")
    # heuristic baseline
    hr=_smallright_construct(sub,20,0.60,1,"bigleft","rank",tiebreak="due")
    hck=check_feasibility(sub,_build_operations([hr[b] for b in range(K)])) if hr and len(hr)==K else None
    hobj=hck["objective"] if hck and hck.get("feasible") else None
    print(f"heuristic(rank+bigleft): obj={hobj} feasible={hck.get('feasible') if hck else None}")
    # ILP (seed pool with heuristic -> feasible warm-start, ILP refines exactly)
    seed = {b: hr[b] for b in range(K)} if hr and len(hr)==K else None
    t0=time.time(); by_block=gen_placements(sub, seed_sol=seed); tgen=time.time()-t0
    poolsz=sum(len(b) for b in by_block)
    print(f"placement pool: {poolsz} (gen {tgen:.1f}s)")
    # Benders loop
    for it in range(5):
        sol,ilpobj,tconf,npl,nconf=solve_ilp(sub,by_block,tl=30)
        if sol is None: print("ILP infeasible/timeout"); return
        ck=check_feasibility(sub,_build_operations([sol[b] for b in range(K)]))
        print(f"  iter{it}: ILP obj={ilpobj:.0f} conf_pairs={nconf}({tconf:.1f}s) -> official feasible={ck['feasible']} obj={ck['objective'] if ck['feasible'] else 'INF'}")
        if ck.get("feasible"):
            print(f"=== ILP obj={ck['objective']:.0f}  vs  heuristic={hobj}  ({'ILP WINS' if hobj and ck['objective']<hobj else 'heuristic'}) ===")
            return
        # no-good cut: forbid this exact selection (A4 Benders)
        viol=set()
        for v in ck.get("violations",[]):
            import re
            for mm in re.findall(r"block[s]? (\d+)",v): viol.add(int(mm))
        # forbid the placements chosen for violating blocks together
        # (simple no-good: at least one of them must change)
        cut=[sol[b] for b in viol if b in sol]
        if not cut: print("cannot extract violation -> stop"); return
        # attach cut for next solve by marking: remove these exact placements
        for b in list(viol):
            by_block[b]=[p for p in by_block[b] if not (p["x"]==sol[b]["x"] and p["y"]==sol[b]["y"] and p["j"]==sol[b]["bay_id"] and p["en"]==sol[b]["entry_time"] and p["o"]==sol[b]["orient_idx"])]
            if not by_block[b]: print(f"block {b} pool exhausted"); return
    print("Benders: max iters reached")

if __name__=="__main__": main()
