"""Does the DIRECTED operator actually reach the master's wish, and is the wish seatable?

masterprobe3 named the moves and priced them: from 86,665, b100 alone is worth 8.3% and three
moves are worth 24.5%, and masterprobe2 showed the refusal is the packer's, not the model's.
BRK_WISH points brk's target and outsider list at that wish instead of at pressure and
single-move gain.

This calls the operator directly on a saved incumbent, both ways, so the comparison is not
buried under a whole pipeline run.  What matters is not only the objective but WHICH blocks
each variant tried to admit -- the undirected one can be doing well for the wrong reason, and a
directed one that never gets its wish seated is worth knowing about before a queue spends
half an hour on it.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib

mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "myalg_brk")
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, "data/hidden/prob_3.json")))
sol = json.load(open("results/p3_incumbent.json"))
sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
n = len(d["blocks"]); m = len(d["bays"])
o0, _ = mod._total(d, sol)
print("incumbent  obj=%d" % int(o0), flush=True)

import bayrepack as R


def assign_of(s):
    a = [-1] * n
    for t, ops in s["operations"].items():
        for op in ops:
            if op["type"] == "ENTRY":
                a[op["block_id"]] = op["bay_id"]
    return a


base_a = assign_of(sol)

for wish in ("0", "1"):
    os.environ["BRK_WISH"] = wish
    R._CALLS[0] = 0
    R._TIERCOST[:] = [80.0, 21.0, 21.0]
    R._WISH_CACHE.clear()
    cur = dict(sol)
    tot = 0.0
    for call in range(3):          # repeated application is where brk's gain compounds
        t = time.time()
        out = R.repack(d, cur, budget, mod._total, mod._build_operations,
                       mod._ogc_fast_engine, hard=budget * 3)
        el = time.time() - t
        tot += el
        if out is None:
            print("  wish=%s call %d  None            (%.0fs)" % (wish, call + 1, el), flush=True)
            break
        cur = {"operations": out["operations"]} if "operations" in out else out
        o, c = mod._total(d, cur)
        a = assign_of(cur)
        moved = [b for b in range(n) if a[b] != base_a[b]]
        print("  wish=%s call %d  obj=%-9d %+7.2f%%  moved %d  %s  (%.0fs)"
              % (wish, call + 1, int(o), 100.0 * (o - o0) / o0, len(moved),
                 ",".join("b%d->%d" % (b, a[b]) for b in moved[:8]), el), flush=True)
    print("  wish=%s total %.0fs" % (wish, tot), flush=True)
