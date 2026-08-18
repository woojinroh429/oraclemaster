# placement 실패/NFP fallback 효용 실측: 각 인스턴스를 NFP fallback OFF(v34기본)/ON으로
# 구성 -> 미배치 블록수, Z1 비교. NFP가 블록을 구제하거나 Z1을 낮추면 견고NFP 가치 있음.
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myalgorithm import _smallright_construct, _build_operations
from utils import check_feasibility

paths=sys.argv[1].split(","); DL=float(sys.argv[2]) if len(sys.argv)>2 else 200.0

def run(prob, nofb):
    os.environ["OGC_NOFALLBACK"]="1" if nofb else "0"
    t=time.time()
    recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank")
    dt=time.time()-t
    placed=len(recs) if recs else 0
    z1=None; feas=None
    if recs and len(recs)==len(prob["blocks"]):
        ck=check_feasibility(prob,_build_operations(list(recs.values())))
        z1=ck["obj1"]; feas=ck["feasible"]
    return placed,z1,feas,dt

for path in paths:
    prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path)); n=len(prob["blocks"])
    p_off,z_off,f_off,d_off=run(prob,True)   # fallback OFF (v34 기본)
    p_on ,z_on ,f_on ,d_on =run(prob,False)  # fallback ON
    flag=""
    if p_on>p_off: flag=" <<< NFP가 미배치 구제!"
    elif z_off is not None and z_on is not None and z_on<z_off-1e-9: flag=" <<< NFP가 Z1 개선!"
    zoff = f"{z_off:.0f}" if z_off is not None else "N/A"
    zon  = f"{z_on:.0f}" if z_on is not None else "N/A"
    print(f"{nm:<10} n={n:<3} | OFF: {p_off}/{n} Z1={zoff:<7} ({d_off:.0f}s) | ON: {p_on}/{n} Z1={zon:<7} ({d_on:.0f}s){flag}",flush=True)
