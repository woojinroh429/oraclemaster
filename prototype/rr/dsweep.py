# 방향 스윕: 8방향 construction Z1/obj 비교 (한 프로세스=한 인스턴스, 순서=rank 고정).
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as M
from myalgorithm import _smallright_construct, _build_operations, _footprint_areas, _demand_ratio
from utils import check_feasibility

DIRS=["bigleft","bigright","bigbottom","bigtop","cornerBL","cornerBR","cornerTL","cornerTR"]

def one(inst, mode, DL, step):
    try:
        recs=_smallright_construct(inst, DL, 0.60, step, mode, "rank", tiebreak="due")
    except Exception as e:
        return None
    if not recs or len(recs)!=len(inst["blocks"]): return None
    ck=check_feasibility(inst, _build_operations(list(recs.values())))
    return ck if ck.get("feasible") else None

def main():
    path=sys.argv[1]; DL=float(sys.argv[2] if len(sys.argv)>2 else 15); step=int(sys.argv[3] if len(sys.argv)>3 else 1)
    inst=json.load(open(path)); name=os.path.basename(path).replace(".json",""); n=len(inst["blocks"])
    ar,bc,_=_footprint_areas(inst); ratio=_demand_ratio(inst,ar,bc)
    res={}
    for d in DIRS:
        ck=one(inst,d,DL,step); res[d]=ck
    bl=res["bigleft"]
    blz=bl["obj1"] if bl else None
    row=f"{name} n={n} r={ratio:.3f} |"
    best=("bigleft", bl["objective"] if bl else 9e18)
    for d in DIRS:
        ck=res[d]
        if ck is None: row+=f" {d}=INF"; continue
        z=ck["obj1"]; o=ck["objective"]
        mark="*" if (blz is not None and z<blz) else ""
        row+=f" {d}={z:.0f}{mark}"
        if o<best[1]: best=(d,o)
    row+=f" || Z1-winner:{min((res[d]['obj1'],d) for d in DIRS if res[d])[1]} obj-best:{best[0]}"
    print(row)

if __name__=="__main__": main()
