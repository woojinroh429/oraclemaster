"""What is the CEILING of free repacking on P3, if you just keep doing it?

Nobody has asked this, and everything else depends on the answer.

harness/p3bay0.py freed one bay, once, and took the objective from 96,990 to 82,175. The `brk`
operator does that repeatedly inside a run and reaches 87,703 on average -- but it is competing
for slices, sizing problems to fit them, and stopping when the budget ends. None of those are
properties of the IDEA; they are properties of the operator.

So take the idea to exhaustion and see where it stops:

    loop:
        for each bay, in order of how much pressure it carries:
            lift every block out of it, add the outsiders that would most improve the
            objective by entering, let cranepack seat maximum value
            rehome anything displaced, for real, against the finished state
            keep it if the grader scores it better
        until a full sweep over every bay improves nothing

Two numbers come out and they point at completely different work:

    ceiling near 70,000    the idea is enough and the remaining job is engineering -- make brk
                           reach what a patient loop reaches, which is a scheduling and sizing
                           problem, not a search one
    ceiling near 85,000    brk is already close to the ceiling of free repacking, more of it
                           will not pay, and 70,000 needs a different mechanism entirely

This is deliberately NOT a time-limited operator. It is allowed to take as long as it takes,
because the question is what the idea is worth, not what fits in 240 s. If the ceiling turns out
to be reachable, the next question -- can it be reached in budget -- is worth asking. If it does
not, that question is moot.

    python3.12 harness/p3ceil.py [PROB] [SOLVE_SECONDS] [SWEEP_SECONDS] [MOD]
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
SWEEP = float(sys.argv[3]) if len(sys.argv) > 3 else 120.0
MOD = sys.argv[4] if len(sys.argv) > 4 else "myalg_base"

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
m = len(d["bays"])
sol = importlib.import_module(MOD).algorithm(d, SOLVE)
o0, c0 = SC._total(d, sol)
print("%s on P%d: obj=%d  Z1=%s Z2=%s Z3=%s  feasible=%s"
      % (MOD, PROB, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3"),
         c0.get("feasible")), flush=True)
print("\n   sweeping every bay until a full pass improves nothing; %.0fs per repack,"
      " no overall time limit" % SWEEP)
print("\n   round  bay      obj        delta   cumulative     secs")

cur, cum, t00 = o0, 0.0, time.time()
rnd = 0
while True:
    rnd += 1
    moved = False
    for j in range(m):
        t = time.time()
        # nout/step/nent are pinned to the large tier, the one brkcost priced at -14.09%.
        # BRK_TARGET names the bay so the sweep covers all of them rather than re-picking the
        # most pressed one every time.
        os.environ["BRK_TARGET"] = str(j)
        out = bayrepack.repack(d, sol, SWEEP, SC._total, SC._build_operations,
                               SC._ogc_fast_engine, nout=40, step=4, nent=3)
        el = time.time() - t
        if out is None:
            print("      %2d   %2d          --            --   %10d   %6.0f"
                  % (rnd, j, int(cur), el), flush=True)
            continue
        o1, c1 = SC._total(d, out)
        if not c1.get("feasible"):
            print("      %2d   %2d    INFEASIBLE -- discarded" % (rnd, j), flush=True)
            continue
        if o1 < cur - 1e-9:
            cum += cur - o1
            print("      %2d   %2d   %9d   %+10d   %10d   %6.0f"
                  % (rnd, j, int(o1), int(o1 - cur), int(cum), el), flush=True)
            sol, cur, moved = out, o1, True
        else:
            print("      %2d   %2d   %9d   %+10d       (kept)   %6.0f"
                  % (rnd, j, int(o1), int(o1 - cur), el), flush=True)
    if not moved:
        break
    if rnd >= 12:
        print("      stopping at 12 rounds -- still improving, so this is a floor on the"
              " ceiling, not the ceiling", flush=True)
        break
os.environ.pop("BRK_TARGET", None)

print("\n[CEILING]  %d -> %d   (%+.2f%%) in %d rounds, %.0fs total"
      % (int(o0), int(cur), 100.0 * (cur - o0) / o0, rnd, time.time() - t00))
print("   brk inside a 240s run averages 87,703, and a control without it averages 103,463.")
if cur <= 75000:
    print("   -> the ceiling is BELOW 75,000, so free repacking is enough on its own and the")
    print("      remaining job is engineering: make the operator reach in budget what this")
    print("      loop reaches with patience.  That is scheduling and sizing, not search.")
elif cur <= 84000:
    print("   -> the ceiling sits between the target and what brk already does.  Worth chasing,")
    print("      but it will not reach 70,000 by itself and something else has to supply the")
    print("      rest.")
else:
    print("   -> brk is ALREADY near the ceiling of free repacking.  More of it will not pay,")
    print("      and 70,000 needs a different mechanism -- this idea is spent.")
print(flush=True)
