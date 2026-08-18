import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

# Decompose objective for dense mid-size instances (P4-type proxies) + weights.
insts = sys.argv[1:] or ["../data/train/prob_%d.json" % i for i in
                         (26,27,28,29,30, 21,22,23,24,25)]
for path in insts:
    inst = json.load(open(path))
    nm = os.path.basename(path).replace(".json","")
    n = len(inst["blocks"])
    w = inst.get("weights", {})
    w1,w2,w3 = w.get("w1",1.0), w.get("w2",1.0), w.get("w3",1.0)
    t0=time.time(); sol=M.algorithm(inst, 60); dt=time.time()-t0
    ck=check_feasibility(inst, sol)
    if not ck["feasible"]:
        print(f"{nm} INFEASIBLE"); continue
    z1,z2,z3 = ck["obj1"],ck["obj2"],ck["obj3"]
    c1,c2,c3 = w1*z1, w2*z2, w3*z3
    tot = ck["objective"]
    print(f"{nm} n={n} w=({w1:.0f},{w2:.0f},{w3:.0f}) obj={tot:.0f} | "
          f"Z1={z1:.0f}(w={c1:.0f},{100*c1/tot:.0f}%) "
          f"Z2={z2:.0f}(w={c2:.0f},{100*c2/tot:.0f}%) "
          f"Z3={z3:.0f}(w={c3:.0f},{100*c3/tot:.0f}%) [{dt:.0f}s]")
print("ALLDONE")
