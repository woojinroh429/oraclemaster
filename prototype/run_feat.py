# 블록의 '모든 변수'로 스코어링: due/area/proc/rel/wid/hgt/work/pref 가중합 순서 탐색.
# 배치=bigleft 고정. baseline {due:1,area:1}=rank(2359 재현되어야 함).
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _smallright_construct, _build_operations
from utils import check_feasibility

path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path)); n=len(prob["blocks"])

COMBOS=[
    ("rank(base)",      {"due":1,"area":1}),
    ("+wid.5",          {"due":1,"area":1,"wid":0.5}),
    ("+hgt.5",          {"due":1,"area":1,"hgt":0.5}),
    ("+proc.5(long1st)",{"due":1,"area":1,"proc":0.5}),
    ("+proc-.5(short)", {"due":1,"area":1,"proc":-0.5}),
    ("+wid+hgt",        {"due":1,"area":1,"wid":0.5,"hgt":0.5}),
    ("widheavy",        {"due":1,"area":0.5,"wid":1.0}),
    ("all",             {"due":1,"area":1,"wid":0.5,"hgt":0.5,"proc":0.3,"work":0.2,"pref":0.2}),
    ("all-geomheavy",   {"due":1,"area":0.7,"wid":0.7,"hgt":0.7,"proc":0.4}),
]
if len(sys.argv)>3:  # 특정 조합만: 인덱스 콤마
    idx=[int(i) for i in sys.argv[3].split(",")]; COMBOS=[COMBOS[i] for i in idx]

print(f"=== {nm} (n={n}) | 다변수 스코어링 (배치=bigleft) | DL={DL:.0f}s ===",flush=True)
for tag,fw in COMBOS:
    t=time.time()
    recs=_smallright_construct(prob,DL,0.60,1,"bigleft","feat",feat_w=fw)
    dt=time.time()-t
    if not recs or len(recs)!=n:
        print(f"  {tag:<18} 실패({len(recs) if recs else 0}/{n}) ({dt:.0f}s)",flush=True); continue
    ck=check_feasibility(prob,_build_operations(list(recs.values())))
    if not ck["feasible"]:
        print(f"  {tag:<18} INFEAS stage={ck['stage']} ({dt:.0f}s)",flush=True); continue
    print(f"  {tag:<18} Z1={ck['obj1']:<7.0f} obj={ck['objective']:<12.0f} Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f} ({dt:.0f}s)",flush=True)
