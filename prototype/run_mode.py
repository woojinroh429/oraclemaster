# 배치 모드 비교(순서=rank 고정). bigleft vs coreperi 등.
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _smallright_construct, _build_operations
from utils import check_feasibility
path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
modes=sys.argv[3].split(",") if len(sys.argv)>3 else ["bigleft","coreperi"]
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path)); n=len(prob["blocks"])
print(f"=== {nm} (n={n}) | 배치모드 비교 (순서=rank) | DL={DL:.0f}s ===",flush=True)
for md in modes:
    t=time.time()
    recs=_smallright_construct(prob,DL,0.60,1,md,"rank")
    dt=time.time()-t
    if not recs or len(recs)!=n:
        print(f"  {md:<10} 실패({len(recs) if recs else 0}/{n}) ({dt:.0f}s)",flush=True); continue
    ck=check_feasibility(prob,_build_operations(list(recs.values())))
    if not ck["feasible"]:
        print(f"  {md:<10} INFEAS stage={ck['stage']} ({dt:.0f}s)",flush=True); continue
    print(f"  {md:<10} Z1={ck['obj1']:<7.0f} obj={ck['objective']:<12.0f} Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f} ({dt:.0f}s)",flush=True)
