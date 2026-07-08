# 밀도 헤드룸 프로브 (sparrow-3d 정신): 혼잡 bay-순간에 블록을 통째로 재배치하며
# bigleft보다 더 많이 동시에 넣을 수 있는지 강한 탐색(랜덤 재시작 + 실제 엔진).
#  넣을 수 있으면 => 밀도 헤드룸 존재(Z1 감소 여지). 없으면 => 크레인 근본한계 확정.
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myalgorithm import _smallright_construct, _ogc_fast_engine
path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
RESTARTS=int(sys.argv[3]) if len(sys.argv)>3 else 400
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path))
B=prob["blocks"]; n=len(B); m=len(prob["bays"])
due=[b["due_date"] for b in B]; rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]
recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank")
R={b:recs[b] for b in range(n)}

# 가장 혼잡한 bay-순간
best=None
for j in range(m):
    tmax=max(R[b]["exit_time"] for b in range(n) if R[b]["bay_id"]==j) if any(R[b]["bay_id"]==j for b in range(n)) else 0
    for t in range(0,tmax+1):
        cnt=sum(1 for b in range(n) if R[b]["bay_id"]==j and R[b]["entry_time"]<=t<R[b]["exit_time"])
        if best is None or cnt>best[0]: best=(cnt,j,t)
K,j,tstar=best
C=[b for b in range(n) if R[b]["bay_id"]==j and R[b]["entry_time"]<=tstar<R[b]["exit_time"]]
# tstar에 대기중이던(릴리즈됐으나 아직 미입장) 블록 = 이 순간 더 넣고싶은 후보
Wt=[b for b in range(n) if rel[b]<=tstar and R[b]["entry_time"]>tstar]
Wt.sort(key=lambda b:due[b])
print(f"=== {nm} | 밀도헤드룸: bay{j} @t={tstar} | bigleft 동시={K} | 대기후보={len(Wt)} ===",flush=True)

def try_pack(order, extra=None):
    """order의 블록들을 모두 en=tstar로 bay j에 넣어 tstar 동시공존 시도(자연 exit=tstar+pt>tstar).
    실제 엔진이 same-level 충돌을 강제. 좌석수 반환."""
    E=_ogc_fast_engine(prob); E.clear_all()
    seated=0
    for b in order:
        res=E.find_best_placement(b,[j],[tstar])
        if res and res[0]:
            _,bj,oi,x,y,ren,rex=res
            try:
                E.add(int(bj),b,int(oi),float(x),float(y),int(ren),int(rex)); seated+=1
            except Exception: pass
    return seated

import random
# 재현성 위해 index로 셔플(스크립트에선 random 허용). 시드 고정.
rng=random.Random(12345)
baseline=len(C)
targetpool=C+Wt[:6]   # C + 대기후보 6개까지
bestseat=0; bestextra=0
t0=time.time()
for it in range(RESTARTS):
    if time.time()-t0>240: break
    od=list(targetpool); rng.shuffle(od)
    # due 급한 것 앞으로 약간 바이어스(50%는 due정렬)
    if it%2==0: od=sorted(targetpool,key=lambda b:due[b])
    s=try_pack(od, None)
    if s>bestseat: bestseat=s
print(f"  강한탐색({it+1} restart): 최대 동시좌석={bestseat} (bigleft={baseline}, 후보풀={len(targetpool)})",flush=True)
if bestseat>baseline:
    print(f"  >>> 헤드룸 발견! bigleft보다 {bestseat-baseline}개 더 넣음 => Z1 감소 여지 (sparrow-3d 정당화)",flush=True)
else:
    print(f"  >>> 헤드룸 없음: bigleft가 이미 최대밀도. 크레인 근본한계 확정.",flush=True)
