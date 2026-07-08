# 실제 submit_v34 엔진(C++ .so + numba + NFP bigleft)에 order="cpsat" 얹어서
# _hybrid_construct 를 그대로 돌리고, 공식 check_feasibility 로 Z1 측정.
# rank(현재 기본) vs cpsat 순서 비교. 배치엔진/평가 전부 사용자 실제 코드.
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _hybrid_construct, _build_operations
from utils import check_feasibility

path = sys.argv[1]
DL   = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
orders = sys.argv[3].split(",") if len(sys.argv) > 3 else ["rank", "cpsat"]
prob = json.load(open(path))
nm = prob.get("name", os.path.basename(path))
n = len(prob["blocks"])
print(f"=== {nm} (n={n}) | 실제 엔진 _hybrid_construct | 배치기 동일, 순서만 비교 ===", flush=True)
print(f"HAVE_CPP={MA.HAVE_CPP} HAVE_OGC_FAST={MA.HAVE_OGC_FAST} HAVE_ORTOOLS={MA.HAVE_ORTOOLS}", flush=True)

for od in orders:
    t = time.time()
    recs = _hybrid_construct(prob, DL, order=od)
    dt = time.time() - t
    if not recs or len(recs) != n:
        print(f"  {od:<7} 실패(placed {len(recs) if recs else 0}/{n}) ({dt:.0f}s)", flush=True)
        continue
    sol = _build_operations(list(recs.values()))
    ck = check_feasibility(prob, sol)
    if not ck["feasible"]:
        print(f"  {od:<7} INFEASIBLE stage={ck['stage']} ({dt:.0f}s) {ck['violations'][:1]}", flush=True)
        continue
    print(f"  {od:<7} Z1={ck['obj1']:<8.0f} obj={ck['objective']:<12.0f} "
          f"Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f} feasible=OK ({dt:.0f}s)", flush=True)
