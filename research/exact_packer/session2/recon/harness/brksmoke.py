"""Does the repack operator actually fire, and does what it returns verify?

The diagnostic that motivated it (harness/p3bay0.py) took P3's base solution from 96,990 to
82,175 by freeing bay 0 and letting cranepack reseat everything -- but it PRICED the three
residents it displaced at their next-best bay rather than finding them a seat there.  That is
the same assumption every earlier P3 diagnostic made, and this night's whole result is that the
assumption is unsafe: a block that "should" fit somewhere frequently does not.

So the operator does the harder thing -- it asks the engine for a real seat for every displaced
block and abandons the repack if any cannot be placed -- and this script checks that the harder
thing still fires, on the real instance, before any 240 s arm depends on it.

    solve -> call repack once directly -> report what it did and whether the grader accepts it

A None here is not necessarily a bug; it can mean the packer found nothing in the slice, or
found something whose displaced blocks had nowhere to go.  Those are different, so they are
reported differently, which is the point of running this rather than reading a silent None out
of a 240 s log.

    python3.12 harness/brksmoke.py [PROB] [SOLVE_SECONDS] [REPACK_SECONDS] [MOD]
"""
import importlib
import os
import json
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402
import bayrepack                 # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SOLVE = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
TL = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
MOD = sys.argv[4] if len(sys.argv) > 4 else "myalg_base"

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
sol = importlib.import_module(MOD).algorithm(d, SOLVE)
o0, c0 = SC._total(d, sol)
print("%s on P%d: obj=%d  Z1=%s Z2=%s Z3=%s  feasible=%s"
      % (MOD, PROB, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3"),
         c0.get("feasible")), flush=True)

for tl in (TL, TL * 2):
    t = time.time()
    out = bayrepack.repack(d, sol, tl, SC._total, SC._build_operations, SC._ogc_fast_engine)
    el = time.time() - t
    if out is None:
        print("   %5.0fs slice: repack returned None after %.1fs" % (tl, el), flush=True)
        continue
    o1, c1 = SC._total(d, out)
    print("   %5.0fs slice: obj %d -> %d  (%+.2f%%)  Z1=%s Z2=%s Z3=%s  feasible=%s  in %.1fs"
          % (tl, int(o0), int(o1), 100.0 * (o1 - o0) / o0,
             c1.get("obj1"), c1.get("obj2"), c1.get("obj3"), c1.get("feasible"), el), flush=True)
    if not c1.get("feasible"):
        print("   FEASIBILITY FAILURE -- the operator returned something the grader rejects,")
        print("   which _total would have scored inf; it must never reach the pool.")
        sys.exit(1)
    # chain it: a repack that pays once may pay again from its own output
    sol, o0 = out, o1

print("\n   repeated application from its own output is where the real gain would be, so the")
print("   second line above is the one that says whether this is a one-shot or an operator.",
      flush=True)
