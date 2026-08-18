# 원래 v34 algorithm()(NFP+ALNS+best-of) vs 방향 best-of 구성 비교. 저밀도 Z2/Z3 실익 확인.
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _smallright_construct, _build_operations
from utils import check_feasibility

path=sys.argv[1]; TL=float(sys.argv[2]) if len(sys.argv)>2 else 60.0
CDL=float(sys.argv[3]) if len(sys.argv)>3 else 40.0
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path)); n=len(prob["blocks"])

# 1) 원래 v34 전체 파이프라인
t=time.time()
sol=MA.algorithm(prob, timelimit=TL)
dt_v=time.time()-t
ckv=check_feasibility(prob, sol)
print(f"=== {nm} (n={n}) ===",flush=True)
print(f"  v34 algorithm()  obj={ckv['objective']:.0f} Z1={ckv['obj1']:.0f} Z2={ckv['obj2']:.0f} Z3={ckv['obj3']:.0f} feas={ckv['feasible']} ({dt_v:.0f}s)",flush=True)

# 2) 방향 best-of 구성
best=None
for md in ["bigleft","bigright","bigtop","coreperi"]:
    recs=_smallright_construct(prob,CDL,0.60,1,md,"rank")
    if not recs or len(recs)!=n: continue
    ck=check_feasibility(prob,_build_operations(list(recs.values())))
    if not ck["feasible"]: continue
    if best is None or ck["objective"]<best[0]:
        best=(ck["objective"],ck["obj1"],ck["obj2"],ck["obj3"],md)
if best:
    o,z1,z2,z3,md=best
    print(f"  방향best-of({md})  obj={o:.0f} Z1={z1:.0f} Z2={z2:.0f} Z3={z3:.0f}",flush=True)
    d=ckv['objective']-o
    print(f"  => 방향이 v34 대비 obj {d:+.0f} ({d/max(1,ckv['objective'])*100:+.1f}%)  {'방향 우세' if d>0 else 'v34 우세'}",flush=True)
