"""Evaluate a swap without re-packing the whole instance.

The swap experiment was measured on a broken scale.  _realise re-seats every block from its
(bay, entry time), and asked to reproduce the CURRENT solution -- same bays, same times, nothing
swapped -- it comes back 43.7% worse, spilling five blocks that no longer fit the bay they
already occupy.  So every candidate swap was being scored against a -44,840 re-packing loss,
which buries a +10,500 preference gain completely.  All 58 rejections say nothing about swaps.

The fix is to stop re-packing.  Lift out exactly the two blocks, leave the other 198 exactly
where they are, and ask the engine for a position for each in its new bay against that untouched
timeline.  Nothing else can move, so nothing else can degrade: the objective changes by the
preference difference and by whatever Z2 the workload shift causes, and by nothing else.

If a position exists for both, the swap is real and can be applied.  If not, it is genuinely
blocked -- which is the answer the earlier runs were supposed to give and could not.
"""
import importlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as M         # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BUILD = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
MOD = sys.argv[3] if len(sys.argv) > 3 else "myalg_base"

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)

sol = importlib.import_module(MOD).algorithm(d, BUILD)
o0, c0 = M._total(d, sol)
print("P%d start obj=%d Z1=%s Z2=%s Z3=%s"
      % (PROB, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3")), flush=True)

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

pref = [B[b]["bay_preferences"] for b in range(n)]
want = [max(range(m), key=lambda j: pref[b][j]) for b in range(n)]
E = M._ogc_fast_engine(d)


def seat(hold_out, b, bay):
    """A feasible (orient, x, y) for b in bay over its own window, against everyone except
    hold_out.  Nothing is moved -- this only asks whether a free slot exists."""
    E.clear_all()
    for q in range(n):
        if q in hold_out:
            continue
        r = rec[q]
        E.add(int(r["bay_id"]), int(q), int(r["orient_idx"]), float(r["x"]), float(r["y"]),
              int(r["entry_time"]), int(r["exit_time"]))
    try:
        out = E.feasible_scan(int(b), [int(bay)], int(rec[b]["entry_time"]),
                              int(rec[b]["exit_time"]), 1)
    except Exception:
        return None
    if not len(out):
        return None
    r = out[0]                       # rows are (bay, orient, ix, iy)
    return (int(r[1]), int(r[2]), int(r[3]))


def pen(b, j):
    return max(pref[b]) - pref[b][j]


pairs = []
for r in range(n):
    jr = rec[r]["bay_id"]
    for q in range(n):
        if q == r or rec[q]["bay_id"] == jr or want[q] != jr:
            continue
        val = (pen(q, rec[q]["bay_id"]) - pen(q, jr)) - (pen(r, rec[q]["bay_id"]) - pen(r, jr))
        if val > 0:
            pairs.append((val, r, q))
pairs.sort(reverse=True)
print("   %d candidate swaps by preference gap" % len(pairs), flush=True)

applied, tried, blocked = 0, 0, 0
t0 = time.time()
for val, r, q in pairs:
    if time.time() - t0 > 400:
        break
    br, bq = rec[r]["bay_id"], rec[q]["bay_id"]
    if br == bq:
        continue
    tried += 1
    pr = seat({r, q}, r, bq)          # the resident, into the outsider's bay
    if pr is None:
        blocked += 1
        continue
    save = dict(rec[r])
    rec[r].update(bay_id=bq, orient_idx=pr[0], x=pr[1], y=pr[2])
    pq = seat({q}, q, br)             # the outsider, into the bay just vacated
    if pq is None:
        rec[r] = save
        blocked += 1
        continue
    saveq = dict(rec[q])
    rec[q].update(bay_id=br, orient_idx=pq[0], x=pq[1], y=pq[2])
    s2 = M._build_operations([rec[b] for b in range(n)])
    ok = M.check_feasibility(d, s2).get("feasible")
    o2 = M._total(d, s2)[0] if ok else float("inf")
    if ok and o2 < o0 - 1e-9:
        o0 = o2
        applied += 1
        print("   swap %-3d <-> %-3d  worth %3.0f  obj=%d" % (r, q, val, int(o2)), flush=True)
    else:
        rec[r], rec[q] = save, saveq

s2 = M._build_operations([rec[b] for b in range(n)])
o1, c1 = M._total(d, s2)
print("P%d local-swap  %d applied, %d blocked, %d tried  obj=%-9d Z1=%s Z2=%s Z3=%s feasible=%s"
      % (PROB, applied, blocked, tried, int(o1), c1.get("obj1"), c1.get("obj2"), c1.get("obj3"),
         M.check_feasibility(d, s2).get("feasible")), flush=True)
