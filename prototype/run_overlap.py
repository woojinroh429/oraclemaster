# sparrow 적용가능성 진단: peak 혼잡 순간, 베이 내 블록 footprint 겹침 비율.
#  sum(개별 footprint 면적)/union 면적.  ~1 이면 겹침없음(2D packable, sparrow 유효),
#  >>1 이면 cross-level(레이어) 겹침 심함(순수2D sparrow 무용, 3D 필요).
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myalgorithm import _smallright_construct
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import affinity
from utils import Block

path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path))
B=prob["blocks"]; n=len(B); m=len(prob["bays"])
recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank")
R={b:recs[b] for b in range(n)}

def footprint(b):
    r=R[b]; blk=Block(block_id=b, block_data=B[b], x=float(r["x"]), y=float(r["y"]), orient_idx=r["orient_idx"])
    polys=[Polygon([(float(p[0]),float(p[1])) for p in L]) for L in blk.resolved_layers()]
    polys=[p for p in polys if p.is_valid and p.area>0]
    u=unary_union(polys)
    return u

# footprint 캐시
FP={b:footprint(b) for b in range(n)}
FA={b:FP[b].area for b in range(n)}

print(f"=== {nm} | footprint 겹침 진단 (peak 순간, 베이별) ===",flush=True)
tmax=max(R[b]["exit_time"] for b in range(n))
for j in range(m):
    ba=prob["bays"][j]["width"]*prob["bays"][j]["height"]
    # 이 베이에서 동시 present 블록수 최대인 순간
    best_t=None; best_k=-1
    for t in range(0,tmax+1):
        pres=[b for b in range(n) if R[b]["bay_id"]==j and R[b]["entry_time"]<=t<R[b]["exit_time"]]
        if len(pres)>best_k: best_k=len(pres); best_t=t
    pres=[b for b in range(n) if R[b]["bay_id"]==j and R[b]["entry_time"]<=best_t<R[b]["exit_time"]]
    sum_a=sum(FA[b] for b in pres)
    uni=unary_union([FP[b] for b in pres]).area if pres else 0
    print(f"  bay{j} (area {ba}) peak@{best_t}: {len(pres)}블록 | sum_footprint={sum_a:.0f} "
          f"union={uni:.0f} | sum/union={sum_a/max(1,uni):.2f} | union/bay={uni/ba*100:.0f}% sum/bay={sum_a/ba*100:.0f}%",flush=True)
print("  해석: sum/union~1 => 겹침없음(2D packable, sparrow 유효) / >>1 => 레이어겹침 심함(순수2D 무용)",flush=True)
