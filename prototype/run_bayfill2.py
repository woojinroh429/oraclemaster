# 엔진 기반 검증: 각 대기블록이 '자기 릴리즈 시각에' 실제로 들어갈 자리가 있었나?
#  있으면 -> placer/순서가 자리를 놓쳐 불필요 대기(개선여지). 없으면 -> 기하적 포화(구조적 지각).
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _smallright_construct, _build_operations, _ogc_fast_engine
from utils import check_feasibility

path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 200.0
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path))
B=prob["blocks"]; n=len(B); m=len(prob["bays"]); bay_list=list(range(m))
print(f"=== {nm} (n={n}) | 엔진기반 대기블록 배치가능성 검증 (rank) | DL={DL:.0f}s ===",flush=True)
recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank")
if not recs or len(recs)!=n:
    print(f"  실패 {len(recs) if recs else 0}/{n}"); sys.exit()
ck=check_feasibility(prob,_build_operations(list(recs.values())))
R=[recs[b] for b in range(n)]
print(f"  Z1={ck['obj1']:.0f} 대기={sum(1 for b in range(n) if R[b]['entry_time']>B[b]['release_time'])} "
      f"지각={sum(1 for b in range(n) if R[b]['exit_time']>B[b]['due_date'])}",flush=True)

waited=[b for b in range(n) if R[b]["entry_time"]>B[b]["release_time"]]
could=0; blocked=0; err=0; t0=time.time()
examples=[]
for b in waited:
    r=B[b]["release_time"]
    try:
        E=_ogc_fast_engine(prob); E.clear_all()
        # r 시각에 present인 다른 블록들을 실제 위치로 배치
        for bb in range(n):
            if bb==b: continue
            if R[bb]["entry_time"]<=r<R[bb]["exit_time"]:
                E.add(R[bb]["bay_id"],bb,R[bb]["orient_idx"],float(R[bb]["x"]),float(R[bb]["y"]),
                      int(R[bb]["entry_time"]),int(R[bb]["exit_time"]))
        res=E.find_best_placement(b,bay_list,[r])
        if res and res[0]:
            could+=1
            if len(examples)<5: examples.append((b, r, R[b]["entry_time"], R[b]["entry_time"]-r))
        else:
            blocked+=1
    except Exception:
        err+=1
    if time.time()-t0>DL:
        print(f"  (시간초과, {could+blocked+err}/{len(waited)}까지)",flush=True); break
tot=could+blocked
print(f"  대기 {len(waited)}개 중 검사 {tot}: '릴리즈시각에 넣을 자리 있었음'={could} ({could/max(1,tot)*100:.0f}%), "
      f"'기하포화(자리없음)'={blocked} ({blocked/max(1,tot)*100:.0f}%), err={err}",flush=True)
if examples:
    print(f"  넣을수있었는데 대기한 예시(block, release, 실제entry, 낭비대기): {examples}",flush=True)
print("  해석: '자리 있었음' 비율↑ = placer가 베이를 덜 채워 불필요 대기→지각(개선여지). "
      "'기하포화'↑ = 진짜 꽉 참(구조적, 순서/배정으론 못 줄임).",flush=True)
