"""Is bay 0 refusing these blocks because of shape, or only because of WHEN they ask?

The swap analysis found 98 profitable exchanges worth -26.98% on P3, and the corrected pair test
found 0 of 7 seatable: leaving bay 0 has thousands of legal cells, entering it has none, even
after the partner vacates.  Bay 0's peak area occupancy is 54%, so the wall is not space.

But every one of those checks asked at the block's OWN entry time.  P3 has Z1 = 0 at a demand
ratio of 0.327, so a block can usually enter earlier or later at no cost in tardiness -- the
whole window [release, due - processing] is free.  A refusal at one instant says nothing about
the others.

So ask across the whole tardiness-free window, for every block that wants into bay 0:

    now       does it fit at its current entry time (the earlier answer)
    free      does it fit at ANY time that costs no tardiness
    blocked   nowhere in the window

If most turn out free, P3's wall is a SCHEDULING one -- the pipeline is choosing entry times
that happen to collide -- and the fix is to let the swap pick its own time.  If most stay
blocked, the wall is geometric and the fix is packing bay 0 so descent paths survive.

Those two conclusions want opposite work, which is why this has to be measured before either.

    python3.12 harness/p3time.py [PROB] [SECONDS] [MOD]
"""
import importlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
MOD = sys.argv[3] if len(sys.argv) > 3 else "myalgorithm"

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
w2, w3 = float(w["w2"]), float(w["w3"])
pref = [B[b]["bay_preferences"] for b in range(n)]
mxp = [max(pref[b]) for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
pt = [int(B[b]["processing_time"]) for b in range(n)]
rel = [int(B[b]["release_time"]) for b in range(n)]
due = [int(B[b]["due_date"]) for b in range(n)]
bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]

sol = importlib.import_module(MOD).algorithm(d, SECS)
cur, ent, ext, place = [0] * n, {}, {}, {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            cur[op["block_id"]] = op["bay_id"]
            ent[op["block_id"]] = int(t)
            place[op["block_id"]] = (op["orient_idx"], op["x"], op["y"])
        else:
            ext[op["block_id"]] = int(t)


def obj_of(assign):
    load = [0.0] * m
    for b in range(n):
        load[assign[b]] += wl[b]
    v = [u[j] * load[j] for j in range(m)]
    return (w2 * math.floor(max(v) - min(v))
            + w3 * sum(mxp[b] - pref[b][assign[b]] for b in range(n)))


base = obj_of(cur)
v0 = [u[j] * sum(wl[b] for b in range(n) if cur[b] == j) for j in range(m)]
TGT = v0.index(max(v0))
print("%s on P%d: obj=%d, contested bay is %d (%.0fx%.0f, u=%.3f)"
      % (MOD, PROB, int(base), TGT, bays[TGT]["width"], bays[TGT]["height"], u[TGT]), flush=True)

# every block NOT in the contested bay that would improve the objective by moving into it
cand = []
for b in range(n):
    if cur[b] == TGT:
        continue
    alt = list(cur)
    alt[b] = TGT
    o = obj_of(alt)
    cand.append((o - base, b))
cand.sort()
print("   %d blocks outside bay %d; the 25 whose move in is worth most:" % (len(cand), TGT))

E = SC._ogc_fast_engine(d)


def seat_at(b, j, t):
    E.clear_all()
    for q in range(n):
        if q == b:
            continue
        oi, x, y = place[q]
        E.add(int(cur[q]), int(q), int(oi), float(x), float(y), int(ent[q]), int(ext[q]))
    return len(E.feasible_scan(int(b), [int(j)], int(t), int(t + pt[b]), 1))


now_ok = free_ok = blocked = 0
free_val = 0.0
print("      delta    blk   at its own time   anywhere tardiness-free    window")
for dlt, b in cand[:25]:
    at_now = seat_at(b, TGT, ent[b])
    lo, hi = rel[b], due[b] - pt[b]
    found = None
    if at_now:
        found = ent[b]
    elif hi >= lo:
        span = hi - lo
        for t in sorted({lo, hi} | {lo + span * i // 12 for i in range(13)}):
            if seat_at(b, TGT, t):
                found = t
                break
    if at_now:
        now_ok += 1
        tag = "yes (%d cells)" % at_now
    elif found is not None:
        free_ok += 1
        free_val += -dlt
        tag = "no -> YES at t=%d" % found
    else:
        blocked += 1
        tag = "no -> blocked everywhere"
    print("      %+8.0f  %-4d  %-15s   %-26s [%d,%d] now %d"
          % (dlt, b, "yes" if at_now else "no", tag, lo, hi, ent[b]))

print("\n   of the 25 most valuable would-be entrants to bay %d:" % TGT)
print("      %2d fit at their own entry time" % now_ok)
print("      %2d fit only at some OTHER tardiness-free time (worth %.0f of objective)"
      % (free_ok, free_val))
print("      %2d fit nowhere in their window" % blocked)
print("   -> %s"
      % ("the wall is SCHEDULING: the pipeline picks colliding entry times, and a swap that may "
         "choose its own time gets in" if free_ok >= blocked else
         "the wall is GEOMETRIC: bay 0 cannot take them at any time, so the fix is packing it so "
         "descent paths survive"), flush=True)
