# corner-best-of 종합 측정: bigleft vs best-of{cornerTL,cornerBL,cornerTR,cornerBR}.
# 구성단계 (순서=rank 고정). 한 프로세스=한 인스턴스.
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as M
from myalgorithm import _smallright_construct, _build_operations, _footprint_areas, _demand_ratio
from utils import check_feasibility

CORNERS=["cornerTL","cornerBL","cornerTR","cornerBR"]

def con(inst, mode, DL, step):
    try:
        recs=_smallright_construct(inst, DL, 0.60, step, mode, "rank", tiebreak="due")
    except Exception:
        return None
    if not recs or len(recs)!=len(inst["blocks"]): return None
    ck=check_feasibility(inst, _build_operations(list(recs.values())))
    return ck if ck.get("feasible") else None

def main():
    path=sys.argv[1]; DL=float(sys.argv[2]); step=int(sys.argv[3])
    inst=json.load(open(path)); name=os.path.basename(path).replace(".json",""); n=len(inst["blocks"])
    ar,bc,_=_footprint_areas(inst); ratio=_demand_ratio(inst,ar,bc)
    bl=con(inst,"bigleft",DL,step)
    cs={c:con(inst,c,DL,step) for c in CORNERS}
    feas=[(cs[c]["objective"],c) for c in CORNERS if cs[c]]
    if bl is None or not feas:
        print(f"{name} r={ratio:.3f} FAIL bl={bl is not None}"); return
    cb=min(feas); cbc=cb[1]; cbo=cb[0]; cbz=cs[cbc]["obj1"]
    dz=100*(bl["obj1"]-cbz)/max(1,bl["obj1"]); do=100*(bl["objective"]-cbo)/max(1,bl["objective"])
    win="corner" if cbo<bl["objective"] else "bigleft"
    print(f"{name}\tr={ratio:.3f}\tbigleft Z1={bl['obj1']:.0f} obj={bl['objective']:.0f}\tcornerBest({cbc}) Z1={cbz:.0f} obj={cbo:.0f}\tdZ1={dz:+.1f}% dobj={do:+.1f}%\t{win}")

if __name__=="__main__": main()
