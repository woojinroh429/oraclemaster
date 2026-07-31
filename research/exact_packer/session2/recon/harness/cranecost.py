"""How much room does the descent rule actually take away?  Count it, do not re-solve for it.

Two attempts to price the crane by relaxing it and re-solving both produced nonsense.  The first
returned false from desc_hit outright, which also deleted 2D collision (there is no separate
overlap test -- placement_feasible_tl screens bounding boxes and then calls desc_hit, whose
j == k term IS ordinary overlap), so blocks stacked through each other.  The second kept j == k
and dropped only j > k, which is the correct relaxation, and still came back at Z1 416,541
against 674, with entry times running to 4417 instead of 59.

That second failure is the informative one.  A relaxed problem cannot be harder, so the packer
is not solving it -- and the reason is that the descent rule is not merely a test the search
passes through, it is what the search STEERS BY.  The contact score, the hard-reject bitmap
("F carries occupancy PLUS crane descent shadows"), and the occupancy map are all built on the
descent shadow.  Remove the rule and the compass goes with it, so the beam loses its way and
defers blocks indefinitely.  Re-solving can therefore never price this constraint.

So measure it where no search is involved.  Take the shipped solution, and for every block ask
the engine, against the real timeline of all the OTHER blocks at that block's own entry window:

    with     how many (orient, x, y) cells are feasible under the full rule
    without  how many are feasible when only j == k is enforced

The ratio is exactly how much of the bay the descent rule sterilises, per block, in the
configuration we actually ship.  No heuristic can distort it and nothing can be made infeasible,
because nothing is moved.

    python3.12 harness/cranecost.py PROB [BUDGET] [MOD]

Run it twice, once with OGC_NOCRANE=1, and pair the two outputs -- the flag changes what
feasible_scan counts, not what the solution is.
"""
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 5
BUDGET = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
MOD = sys.argv[3] if len(sys.argv) > 3 else "myalg_base"
TAG = os.environ.get("OGC_NOCRANE", "0")

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B = d["blocks"]
n = len(B)
m = len(d["bays"])

sol = importlib.import_module(MOD).algorithm(d, BUDGET)
o0, c0 = SC._total(d, sol)
print("P%d %s  obj=%d Z1=%s Z2=%s Z3=%s   (OGC_NOCRANE=%s)"
      % (PROB, MOD, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3"), TAG), flush=True)

rec = {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            rec[op["block_id"]] = {"bay": op["bay_id"], "oi": op["orient_idx"],
                                   "x": op["x"], "y": op["y"], "en": int(t)}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "EXIT":
            rec[op["block_id"]]["ex"] = int(t)

E = SC._ogc_fast_engine(d)
tot_own, tot_all, zero_own = 0, 0, 0
per_bay_own = [0] * m
per_bay_all = [0] * m
for b in range(n):
    E.clear_all()
    for q in range(n):
        if q == b:
            continue
        r = rec[q]
        E.add(int(r["bay"]), int(q), int(r["oi"]), float(r["x"]), float(r["y"]),
              int(r["en"]), int(r["ex"]))
    r = rec[b]
    own = len(E.feasible_scan(int(b), [int(r["bay"])], int(r["en"]), int(r["ex"]), 1))
    allb = len(E.feasible_scan(int(b), list(range(m)), int(r["en"]), int(r["ex"]), 1))
    tot_own += own
    tot_all += allb
    per_bay_own[r["bay"]] += own
    per_bay_all[r["bay"]] += allb
    if own == 0:
        zero_own += 1

print("   cells available to each block against the real timeline, at its own entry window:")
print("      in its OWN bay : %s  (mean %.1f per block, %d blocks had none)"
      % (format(tot_own, ","), tot_own / float(n), zero_own))
print("      across ALL bays: %s  (mean %.1f per block)"
      % (format(tot_all, ","), tot_all / float(n)))
print("   per bay (own-bay residents): %s" % [per_bay_own[j] for j in range(m)])
print("PAIRME P%d nocrane=%s own=%d all=%d zero=%d" % (PROB, TAG, tot_own, tot_all, zero_own),
      flush=True)
