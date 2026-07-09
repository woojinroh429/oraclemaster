# 실 solver algorithm() full A/B: WLNS_REFINE off vs on. 한 프로세스=한 인스턴스.
# 사용: WLNS_REFINE=<0|1> python3.12 ab_full.py <inst.json> <timelimit>
import os, sys, json, time
sys.path.insert(0, os.environ.get("ENGINE_DIR","../sv34"))
import myalgorithm as M
from myalgorithm import _footprint_areas, _demand_ratio
from utils import check_feasibility

inst=json.load(open(sys.argv[1])); tl=float(sys.argv[2] if len(sys.argv)>2 else 60)
name=os.path.basename(sys.argv[1]).replace(".json",""); n=len(inst["blocks"])
ar,bc,_=_footprint_areas(inst); ratio=_demand_ratio(inst,ar,bc)
t0=time.time(); sol=M.algorithm(inst, tl); dt=time.time()-t0
ck=check_feasibility(inst, sol)
mode=os.environ.get("WLNS_REFINE","1")
print(f"{name}\tn={n}\tratio={ratio:.3f}\trefine={mode}\tfeasible={ck['feasible']}\tZ1={ck['obj1']:.0f}\tobj={ck['objective']:.0f}\t{dt:.0f}s")
