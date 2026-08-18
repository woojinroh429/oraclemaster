"""Can the yard physically hold the assignment CP-SAT says is best?

The anchored regrow answers a compound question -- is the assignment good AND can a 120s beam
find it -- and the beam is the weaker half: unanchored at 120s it returned Z3 890 against the
incumbent's 566, so a bad result there would not tell us which half failed.

This asks the physical half on its own.  Fix every block's bay to the CP-SAT assignment, keep
the incumbent's entry and exit times exactly, and walk the blocks in dispatch order asking the
engine for any feasible cell in that one bay.  Nothing is optimised and no beam is involved --
it is a placement feasibility probe.

    every block seated   the assignment is realisable, Z3 falls to the CP-SAT value, and the
                         only remaining problem is getting the search to find it
    many blocks spill    the assignment is a fiction of the area relaxation: it fits by area but
                         not by shape and crane, and the bound it implies is unreachable

Dispatch order matters for a first-fit walk, so several are tried and the best kept.  Blocks
that cannot be seated at their own time are retried across their zero-tardiness slack before
being counted as spilled, since a spill that a free time-shift repairs is not a real one.

    python3.12 harness/realise.py PROB [BUDGET] [MOD] [ANCHOR.json]
"""
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BUDGET = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
MOD = sys.argv[3] if len(sys.argv) > 3 else "myalg_base"
ANC = sys.argv[4] if len(sys.argv) > 4 else os.path.join(HERE, "results/anchor_p%d.json" % PROB)

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays = d["blocks"], d["bays"]
n, m = len(B), len(bays)

asg = [int(v) for v in json.load(open(ANC))["assignment"]]
sol = importlib.import_module(MOD).algorithm(d, BUDGET)
o0, c0 = SC._total(d, sol)
print("P%d incumbent obj=%d Z1=%s Z2=%s Z3=%s" % (PROB, int(o0), c0.get("obj1"), c0.get("obj2"),
                                                  c0.get("obj3")), flush=True)

rec = {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            rec[op["block_id"]] = {"block_id": op["block_id"], "bay_id": op["bay_id"],
                                   "orient_idx": op["orient_idx"], "x": op["x"], "y": op["y"],
                                   "entry_time": int(t)}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "EXIT":
            rec[op["block_id"]]["exit_time"] = int(t)

pt = [int(B[b]["processing_time"]) for b in range(n)]
rel = [int(B[b]["release_time"]) for b in range(n)]
due = [int(B[b]["due_date"]) for b in range(n)]
E = SC._ogc_fast_engine(d)

ORDERS = {
    "entry":  sorted(range(n), key=lambda b: (rec[b]["entry_time"], b)),
    "edd":    sorted(range(n), key=lambda b: (due[b], b)),
    "bigfirst": sorted(range(n), key=lambda b: (-pt[b], b)),
}

best = None
for name, order in ORDERS.items():
    E.clear_all()
    placed, spill, shifted = {}, [], 0
    for b in order:
        en, ex = rec[b]["entry_time"], rec[b]["exit_time"]
        got = None
        # its own time first, then anywhere in the slack that costs no tardiness
        times = [en] + [t for t in range(rel[b], due[b] - pt[b] + 1) if t != en]
        for t in times[:40]:
            r = E.feasible_scan(int(b), [int(asg[b])], int(t), int(t + pt[b]), 1)
            if len(r):
                got = (int(r[0][1]), int(r[0][2]), int(r[0][3]), t, t + pt[b])
                if t != en:
                    shifted += 1
                break
        if got is None:
            spill.append(b)
            continue
        oi, ix, iy, t0, t1 = got
        E.add(int(asg[b]), int(b), oi, float(ix), float(iy), int(t0), int(t1))
        placed[b] = {"block_id": b, "bay_id": asg[b], "orient_idx": oi, "x": ix, "y": iy,
                     "entry_time": t0, "exit_time": t1}
    print("   order=%-9s seated %3d/%d  (%d needed a free time shift)  spilled %d"
          % (name, len(placed), n, shifted, len(spill)), flush=True)
    if best is None or len(spill) < best[0]:
        best = (len(spill), name, placed, spill)

nsp, name, placed, spill = best
if nsp:
    # everything that spilled keeps its incumbent placement, so the result is still a complete
    # solution and its Z3 is an honest partial realisation rather than a fantasy
    for b in spill:
        placed[b] = dict(rec[b])
s2 = SC._build_operations([placed[b] for b in range(n)])
o1, c1 = SC._total(d, s2)
fz = SC.check_feasibility(d, s2)
print("P%d best order=%s  %d spilled kept at their incumbent bay" % (PROB, name, nsp))
print("   realised obj=%-9d Z1=%-6s Z2=%-6s Z3=%-7s feasible=%s   (%+.2f%% vs incumbent)"
      % (int(o1), c1.get("obj1"), c1.get("obj2"), c1.get("obj3"), fz.get("feasible"),
         100.0 * (o1 - o0) / o0), flush=True)
