# 인스턴스 특징 추출(solving 없음, 즉시). 방향 승자와 상관분석용.
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myalgorithm import _footprint_areas, _demand_ratio

def feats(path):
    prob=json.load(open(path)); B=prob["blocks"]; bays=prob["bays"]
    n=len(B); m=len(bays)
    ar,cap,SC=_footprint_areas(prob)
    dens=_demand_ratio(prob,ar,cap)
    areas=[a/SC for a in ar]
    amean=sum(areas)/n; amax=max(areas)
    avar=sum((a-amean)**2 for a in areas)/n; acv=(avar**0.5)/amean if amean else 0
    # 베이 종횡비
    asp=[bays[j]["width"]/bays[j]["height"] for j in range(m)]
    asp_mean=sum(asp)/m; asp_max=max(asp)
    baycap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
    cap_cv=(sum((c-sum(baycap)/m)**2 for c in baycap)/m)**0.5/(sum(baycap)/m)  # 베이크기 편차
    # 큰블록 비중(면적 상위35%가 총면적의 몇%)
    srt=sorted(areas,reverse=True); topk=int(0.35*n)
    bigfrac=sum(srt[:topk])/sum(areas) if areas else 0
    amax_mean=amax/amean if amean else 0
    # 여유(slack): due-release-proc
    slk=[B[i]["due_date"]-B[i]["release_time"]-B[i]["processing_time"] for i in range(n)]
    slk_mean=sum(slk)/n; neg_slk=sum(1 for s in slk if s<0)/n  # 구조적 지각 비율
    horizon=max(B[i]["due_date"] for i in range(n))
    rel_spread=(max(B[i]["release_time"] for i in range(n))-min(B[i]["release_time"] for i in range(n)))/max(1,horizon)
    return dict(n=n, m=m, dens=round(dens,2), acv=round(acv,2), amax_mean=round(amax_mean,1),
                bigfrac=round(bigfrac,2), asp_mean=round(asp_mean,1), asp_max=round(asp_max,1),
                cap_cv=round(cap_cv,2), slk_mean=round(slk_mean,0), neg_slk=round(neg_slk,2),
                rel_spread=round(rel_spread,2))

paths=sys.argv[1:]
print(f"{'inst':<10} {'n':>4} {'m':>2} {'dens':>5} {'acv':>5} {'amax/mn':>7} {'bigfr':>5} {'asp':>4} {'aspmx':>5} {'capcv':>5} {'slk':>6} {'negslk':>6} {'relsp':>5}")
for p in paths:
    nm=os.path.basename(p).replace('.json','')
    f=feats(p)
    print(f"{nm:<10} {f['n']:>4} {f['m']:>2} {f['dens']:>5} {f['acv']:>5} {f['amax_mean']:>7} {f['bigfrac']:>5} {f['asp_mean']:>4} {f['asp_max']:>5} {f['cap_cv']:>5} {f['slk_mean']:>6.0f} {f['neg_slk']:>6} {f['rel_spread']:>5}")
