"""One full portfolio solve in an isolated process. Reads CPPREPAIR from env.
Prints: <objective> <feasible>."""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

path = sys.argv[1]
tl = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
inst = json.load(open(path))
t0 = time.time()
sol = M.algorithm(inst, tl)
dt = time.time() - t0
ck = check_feasibility(inst, sol)
print(f"OBJ {ck['objective'] if ck['feasible'] else 'INFEAS'} FEAS {ck['feasible']} "
      f"Z1 {ck.get('obj1','?')} Z2 {ck.get('obj2','?')} Z3 {ck.get('obj3','?')} DT {dt:.0f}", flush=True)
