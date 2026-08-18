import json, os, sys
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import myalgorithm as M
from utils import check_feasibility
def find(nm):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
for nm in sys.argv[1:]:
    d=json.load(open(find(nm))); w=d["weights"]
    best=None
    for _ in range(2):
        sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
        if ck["feasible"] and (best is None or ck["objective"]<best[0]): best=(ck["objective"],ck["obj1"],ck["obj2"],ck["obj3"])
    o,o1,o2,o3=best
    print(f"{nm}: obj={o:.0f}  Z1={o1:.0f}(w1{int(w['w1'])}) Z2={o2:.0f}(w2{int(w['w2'])}={w['w2']*o2:.0f}) Z3={o3:.0f}(w3{int(w['w3'])}={w['w3']*o3:.0f})",flush=True)
