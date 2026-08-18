"""How long does the repack actually take when you ask it for N seconds?

cranepack's time_budget_s is not a hard limit.  Measured on the real hidden P3: the same call at
grid step 4 (70 blocks, 3 entry times each) returned inside its 120 s ask, and at step 2 -- four
times the position grid -- ran 18 minutes against the same 120 s.  A 9x overrun.

Inside a diagnostic that costs a blocked queue.  Inside the operator it is worse: the allocator
hands out a slice and expects it back, and at the grader's hard time limit an overrun is not a
wasted experiment, it is a missing answer.  There is no knob that makes the packer stop, so
bayrepack instead sizes the PROBLEM to the slice -- positions per orientation, candidate blocks,
and entry times each shrink together when the slice is short.

That rule is only worth having if the numbers behind it are real, so measure them: for each
slice the operator can be handed, what does it actually take, and what does it find?

    slice  the budget passed in, which selects a (step, nout, nent) triple inside the operator
    took   wall clock, which is the number that matters
    ratio  took / slice -- 1.0 means honest, 9.0 is what step 2 did
    gain   what the repack was worth, so a safe setting that finds nothing is visible as such

    python3.12 harness/brkcost.py [PROB] [SOLVE_SECONDS] [MOD]
"""
import importlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402
import bayrepack                 # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SOLVE = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
MOD = sys.argv[3] if len(sys.argv) > 3 else "myalg_base"

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
sol = importlib.import_module(MOD).algorithm(d, SOLVE)
o0, _c = SC._total(d, sol)
print("%s on P%d: obj=%d" % (MOD, PROB, int(o0)), flush=True)
print("\n   slice   step nout nent      took   ratio        obj   gain")

for slice_s in (8.0, 12.0, 20.0, 35.0, 60.0, 100.0):
    bayrepack._CALLS[0] = 0            # same target bay every time, so only the slice varies
    t = time.time()
    out = bayrepack.repack(d, sol, slice_s, SC._total, SC._build_operations, SC._ogc_fast_engine)
    el = time.time() - t
    if out is None:
        print("   %5.0fs   %s      %6.1fs  %5.1fx   %10s  %6s"
              % (slice_s, "auto", el, el / slice_s, "-", "none"), flush=True)
        continue
    o1, c1 = SC._total(d, out)
    print("   %5.0fs   %s      %6.1fs  %5.1fx   %10d  %+6.2f%%%s"
          % (slice_s, "auto", el, el / slice_s, int(o1), 100.0 * (o1 - o0) / o0,
             "" if c1.get("feasible") else "   INFEASIBLE"), flush=True)

print("\n   a ratio near 1 means the sizing rule holds and the operator can be trusted with the")
print("   allocator's slice.  anything above ~2 means the rule is too loose at that slice and")
print("   the triple for it has to come down, because the grader's limit does not forgive.",
      flush=True)
