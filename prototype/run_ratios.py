# 여러 ratio 후보를 40개 인스턴스에 계산 -> 사용자의 0.6/0.7 임계값과 맞는 지표 식별.
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myalgorithm import _footprint_areas, _demand_ratio

def ratios(path):
    prob=json.load(open(path)); B=prob["blocks"]; bays=prob["bays"]; n=len(B); m=len(bays)
    ar,cap,SC=_footprint_areas(prob)
    areas=[a/SC for a in ar]
    baycap=sum(bays[j]["width"]*bays[j]["height"] for j in range(m))
    horizon=max(B[i]["due_date"] for i in range(n))
    peak=_demand_ratio(prob,ar,cap)                             # peak 수요/용량
    # 시간평균 공간-시간 이용률
    tavg=sum(areas[i]*B[i]["processing_time"] for i in range(n))/(baycap*horizon)
    # release~due 창 기준 평균 이용률
    span=sum(max(1,B[i]["due_date"]-B[i]["release_time"]) for i in range(n))/n
    # 정적 면적비(동시성 무시)
    stat=sum(areas)/baycap
    return peak, tavg, stat

paths=sys.argv[1:]
print(f"{'inst':<10}{'peak':>7}{'tavg':>7}{'stat':>7}")
rows=[]
for p in paths:
    nm=os.path.basename(p).replace('.json','')
    pk,tv,st=ratios(p); rows.append((nm,pk,tv,st))
    print(f"{nm:<10}{pk:>7.2f}{tv:>7.2f}{st:>7.2f}")
