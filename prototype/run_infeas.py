# infeasible 구성 원인 진단: 위반 종류(stage)와 예시.
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myalgorithm import _smallright_construct, _build_operations
from utils import check_feasibility
path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 60.0
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path)); n=len(prob["blocks"])
os.environ["OGC_NOFALLBACK"]="1"
recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank")
print(f"{nm} n={n} placed={len(recs)}",flush=True)
ck=check_feasibility(prob,_build_operations(list(recs.values())))
print(f"feasible={ck['feasible']} stage={ck['stage']} 위반수={len(ck['violations'])}",flush=True)
for v in ck["violations"][:6]:
    print("  -",v,flush=True)
