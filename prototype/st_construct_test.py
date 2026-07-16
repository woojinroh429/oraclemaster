"""Raw construction-quality A/B: does the space-time (3DTCS) construction beat the
shipped constructions BEFORE any ALNS? Compares full-solution objective of:
  - engine    : _cppnfp_construct (bottom-left C++)
  - bottomleft: _construct (Python _try_place_block, bottom-left tie-break)
  - spacetime : _st_construct (contact-maximising, static release order)
  - st-dynamic: _st_construct dynamic=True (least-slack selection)
Leftovers filled with _try_place_block; check_feasibility for the objective.
"""
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

def fill_and_obj(inst, state):
    n_bays = len(inst["bays"])
    placed = set(state.assign.keys())
    for b in range(len(inst["blocks"])):
        if b not in placed:
            M._try_place_block(state, b, list(range(n_bays)), time.time()+30)
    if len(state.assign) != len(inst["blocks"]):
        return None
    ck = check_feasibility(inst, M._build_operations(list(state.assign.values())))
    return ck if ck["feasible"] else None

def main():
    for p in sys.argv[1:]:
        inst = json.load(open(p)); nm = os.path.basename(p).replace(".json", "")
        od = rel_order(inst)
        rows = {}
        # engine
        dl = time.time()+30
        a = M._cppnfp_construct(inst, od, dl); st = M._state_from_assign(inst, a)
        rows["engine"] = fill_and_obj(inst, st)
        # bottom-left python
        st = M._construct(inst, od, time.time()+30); rows["bottomleft"] = fill_and_obj(inst, st)
        # space-time static
        st = M._st_construct(inst, od, time.time()+30, dynamic=False); rows["spacetime"] = fill_and_obj(inst, st)
        # space-time dynamic
        st = M._st_construct(inst, od, time.time()+30, dynamic=True); rows["st-dynamic"] = fill_and_obj(inst, st)
        print(f"== {nm} ({len(inst['blocks'])} blks) ==", flush=True)
        base = rows["engine"]["objective"] if rows["engine"] else None
        for k in ("engine", "bottomleft", "spacetime", "st-dynamic"):
            ck = rows[k]
            if ck is None:
                print(f"   {k:12s} INFEASIBLE/incomplete", flush=True); continue
            o = ck["objective"]; d = (100*(o-base)/base) if base else 0
            print(f"   {k:12s} {o:14.0f}  Z1={ck.get('obj1',0):<7.0f} Z3={ck.get('obj3',0):<7.0f}  {d:+.1f}% vs engine", flush=True)
    print("ALLDONE")

if __name__ == "__main__":
    main()
