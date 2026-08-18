"""Focused gate: engine bottom-left vs 3DTCS full-scan construction only, with a
generous deadline so the (slow Python) full scan actually completes all blocks."""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

def area(bd):
    bb = M._orient_bbox(bd, 0); return (bb[2]-bb[0])*(bb[3]-bb[1])

def rel_order(inst):
    B = inst["blocks"]; n = len(B)
    return sorted(range(n), key=lambda b: (B[b]["release_time"],
                  -(B[b]["processing_time"]*area(B[b])), B[b]["due_date"]))

def fobj(inst, st):
    nb = len(inst["bays"]); placed = set(st.assign.keys())
    for b in range(len(inst["blocks"])):
        if b not in placed:
            M._try_place_block(st, b, list(range(nb)), time.time()+60)
    if len(st.assign) != len(inst["blocks"]):
        return None
    ck = check_feasibility(inst, M._build_operations(list(st.assign.values())))
    return ck if ck["feasible"] else None

p = sys.argv[1]; dl = float(sys.argv[2]) if len(sys.argv) > 2 else 120
inst = json.load(open(p)); nm = os.path.basename(p).replace(".json", "")
od = rel_order(inst)
a = M._cppnfp_construct(inst, od, time.time()+30); e = fobj(inst, M._state_from_assign(inst, a))
st = M._st_construct(inst, od, time.time()+dl, dynamic=False); s = fobj(inst, st)
eo = e["objective"] if e else None
if s and eo:
    print(f"{nm}: engine {eo:.0f} (Z1={e['obj1']:.0f}) | 3DTCS {s['objective']:.0f} "
          f"(Z1={s['obj1']:.0f}) | {100*(s['objective']-eo)/eo:+.1f}%", flush=True)
else:
    print(f"{nm}: engine={eo} 3dtcs={'incomplete' if not s else s['objective']}", flush=True)
print("ALLDONE")
