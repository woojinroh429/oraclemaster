"""Direct _alns A/B: build one construction, run _alns OFF vs ON from the SAME
start state, report final objective + iteration count. Instruments iters by
monkey-counting _cpp_reinsert / _try_place_block calls."""
import os, sys, json, time, random
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

path = sys.argv[1]
tl = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
inst = json.load(open(path))
bay_unit = M._bay_unit_weights(inst["bays"])
n = len(inst["blocks"])
rel = [inst["blocks"][b]["release_time"] for b in range(n)]
order = sorted(range(n), key=lambda b: (rel[b], b))

def build_state():
    a = M._cppnfp_construct(inst, order, time.time() + 10)
    return M._rebuild_state_from_assign(inst, a)

def run(mode):
    os.environ["CPPREPAIR"] = str(mode)
    # count repair calls
    cnt = {"cpp": 0, "py": 0}
    orig_cpp = M._cpp_reinsert
    orig_py = M._try_place_block
    def wrap_cpp(*a, **k):
        cnt["cpp"] += 1
        return orig_cpp(*a, **k)
    def wrap_py(*a, **k):
        cnt["py"] += 1
        return orig_py(*a, **k)
    M._cpp_reinsert = wrap_cpp
    M._try_place_block = wrap_py
    st = build_state()
    base = M._objective(list(st.assign.values()), inst, bay_unit)[0]
    rng = random.Random(999)
    t0 = time.time()
    improved, _ = M._alns(inst, st, bay_unit, time.time() + tl, rng, absorb=False)
    dt = time.time() - t0
    M._cpp_reinsert = orig_cpp
    M._try_place_block = orig_py
    sol = M._build_operations(list(improved.values()))
    ck = check_feasibility(inst, sol)
    return base, ck["objective"], ck["feasible"], cnt, dt

for mode in (0, 1):
    base, obj, feas, cnt, dt = run(mode)
    lbl = "ON " if mode else "OFF"
    print(f"CPPREPAIR={lbl}  base={base:.0f} -> final={obj:.0f} feas={feas}  "
          f"repair_calls: cpp={cnt['cpp']} py={cnt['py']}  ({dt:.0f}s)", flush=True)
print("ALLDONE")
