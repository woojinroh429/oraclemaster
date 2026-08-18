# 검증: 지각을 줄이려면 모든 베이를 잘 채워야 함. rank 해에서
#  (1) 베이별 활용도(peak/평균, 면적·폭)  (2) 블록이 '대기'하는 시각에 베이에 여유가 있는지
#      = 대기(released·미배치) 면적 vs 그 시각 전체 여유면적/베이별 여유폭.
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _smallright_construct, _build_operations, _footprint_areas, _orient_bbox
from utils import check_feasibility

path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 200.0
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path))
B=prob["blocks"]; bays=prob["bays"]; n=len(B); m=len(bays)
areas,_,SC=_footprint_areas(prob)  # min-orient footprint*10
bay_area=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
bay_w=[bays[j]["width"] for j in range(m)]

print(f"=== {nm} (n={n}, bays={m}) | 베이 채움 검증 (rank) | DL={DL:.0f}s ===",flush=True)
recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank")
if not recs or len(recs)!=n:
    print(f"  실패 {len(recs) if recs else 0}/{n}"); sys.exit()
ck=check_feasibility(prob,_build_operations(list(recs.values())))
print(f"  Z1={ck['obj1']:.0f} feasible={ck['feasible']}",flush=True)
R=[recs[b] for b in range(n)]

# placed-orientation bbox width/area
def owh(b):
    x0,y0,x1,y1=_orient_bbox(B[b],R[b]["orient_idx"]); return (x1-x0,y1-y0)
pw=[owh(b)[0] for b in range(n)]; parea=[areas[b]/SC for b in range(n)]

tmax=max(R[b]["exit_time"] for b in range(n))
tmin=min(B[b]["release_time"] for b in range(n))

# --- (1) 베이별 활용도 ---
print("  --- 베이별 활용도 ---",flush=True)
occA=[[0.0]*(tmax+1) for _ in range(m)]; occW=[[0.0]*(tmax+1) for _ in range(m)]
cnt=[0]*m
for b in range(n):
    j=R[b]["bay_id"]; cnt[j]+=1
    for t in range(R[b]["entry_time"],R[b]["exit_time"]):
        occA[j][t]+=parea[b]; occW[j][t]+=pw[b]
for j in range(m):
    pkA=max(occA[j])/bay_area[j]; avA=sum(occA[j][tmin:tmax])/max(1,(tmax-tmin))/bay_area[j]
    pkW=max(occW[j])/bay_w[j]; avW=sum(occW[j][tmin:tmax])/max(1,(tmax-tmin))/bay_w[j]
    print(f"    bay{j} (W{bays[j]['width']}xH{bays[j]['height']}): 블록{cnt[j]:>3}  "
          f"면적 peak {pkA*100:4.0f}% 평균 {avA*100:4.0f}% | 폭 peak {pkW*100:4.0f}% 평균 {avW*100:4.0f}%",flush=True)

# --- (2) 대기 시각에 베이 여유 있는지 ---
# 블록 b 대기구간 [release, entry). 그 구간의 각 시각 t에서 전체여유면적, 최대여유폭.
print("  --- 대기(지각원인) 블록: 대기중 베이 여유 진단 ---",flush=True)
waited=[b for b in range(n) if R[b]["entry_time"]>B[b]["release_time"]]
tardy=[b for b in range(n) if R[b]["exit_time"]>B[b]["due_date"]]
print(f"    대기한 블록 {len(waited)}/{n}, 지각 블록 {len(tardy)}/{n}",flush=True)

# 각 대기블록에 대해: 대기 시작시각 r 에서 (그 블록 제외) 각 베이 여유폭 최댓값이
# 이 블록 폭 이상인가? = '폭 기준으론 들어갈 자리가 있었는데 왜 대기?' 신호.
import collections
fit_by_width=0; blocked_all=0
freeW_hist=[]
for b in waited:
    r=B[b]["release_time"]
    # r 시각에 각 베이에 present인 블록들(자기 제외)의 폭 합 -> 여유폭
    maxfree=-1;
    for j in range(m):
        used=0.0
        for bb in range(n):
            if bb==b: continue
            if R[bb]["bay_id"]==j and R[bb]["entry_time"]<=r<R[bb]["exit_time"]:
                used+=pw[bb]
        free=bay_w[j]-used
        if free>maxfree: maxfree=free
    freeW_hist.append((maxfree,pw[b]))
    if maxfree>=pw[b]-1e-9: fit_by_width+=1
    else: blocked_all+=1
print(f"    대기블록 중 '릴리즈 시각에 폭기준 여유가 있던' 수: {fit_by_width}/{len(waited)}  "
      f"(전 베이 폭 부족: {blocked_all})",flush=True)
# 요약: 폭 여유가 있었는데 대기 = 세로/기하/크레인 제약 또는 placer가 안넣음.
avgfreeW = sum(f for f,_ in freeW_hist)/max(1,len(freeW_hist))
print(f"    대기블록 릴리즈시 평균 최대여유폭={avgfreeW:.1f} (블록평균폭={sum(pw[b] for b in waited)/max(1,len(waited)):.1f})",flush=True)

# --- (3) 전 구간 총 여유면적 vs 대기면적 타임라인 (요약: 여유가 남는 시간대 비율) ---
tot_area=sum(bay_area)
slack_times=0; busy_times=0
for t in range(tmin,tmax):
    freeA=tot_area-sum(occA[j][t] for j in range(m))
    waitA=sum(parea[b] for b in range(n) if B[b]["release_time"]<=t<R[b]["entry_time"])
    if waitA>0:
        if freeA>=min(parea[b] for b in range(n)):  # 가장 작은 블록이라도 들어갈 여유
            slack_times+=1
        else: busy_times+=1
span=max(1,slack_times+busy_times)
print(f"    대기존재 시각 중: 여유면적 남는 시각 {slack_times} ({slack_times/span*100:.0f}%), "
      f"포화 시각 {busy_times} ({busy_times/span*100:.0f}%)",flush=True)
print("  해석: '여유남는 시각/폭여유 있는데 대기' 비율이 높으면 = 베이를 덜 채워 지각 유발(개선여지).",flush=True)
