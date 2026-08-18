"""Best-bay-first construction, with REAL geometry, against what the beam produces.

    usage: python3.12 harness/z3first.py <prob> [--data DIR] [--horizon N] [--step N] [--fallback]

The area-only estimate said assigning every block its most-preferred bay and scheduling each bay by
EDD is worth -97.2% on prob_1 and -98.4% on prob_24, and +183% / +394% on prob_6 / prob_20 -- a
split that follows how much of the objective is w3*Z3.  That estimate used AREA as the resource,
and area-feasible is not placement-feasible, which is the one thing the engine exists to decide.

So this does the same construction through the engine's own feasibility path: for each block in EDD
order, take its best bay, walk entry times up from its release, and ask feasible_scan_win for a real
(orientation, x, y).  The first hit is committed with add(), which makes it visible to every later
block.  No contact scoring, no beam, no operators -- the point is to price the assignment, not to
compete with the search.

--fallback lets a block that cannot be placed in its best bay try the remaining bays in preference
order, which is what any usable version of this would do.  Without it, a block that does not fit its
favourite is simply reported unplaced, which measures how binding geometry is on its own.

Prints the full objective through _total, so the number is comparable with every other cell in
results/audit -- and prints the placement failures, because a construction that leaves blocks out is
not a solution however good its objective looks.
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ap = argparse.ArgumentParser()
ap.add_argument("prob", type=int)
ap.add_argument("--data", default="data/stage2")
ap.add_argument("--horizon", type=int, default=0, help="0 = max due + max processing + slack")
ap.add_argument("--step", type=int, default=1)
ap.add_argument("--fallback", action="store_true", help="try other bays in preference order")
ap.add_argument("--objaware", action="store_true",
                help="choose the bay by w1*tardy + w3*penalty instead of by preference")
ap.add_argument("--tag", default="")
a = ap.parse_args()

import myalgorithm as M

prob = json.load(open(os.path.join(a.data, "prob_%d.json" % a.prob)))
BL = prob["blocks"]
n = len(BL)
nbay = len(prob["bays"])
rel = [int(b["release_time"]) for b in BL]
due = [int(b["due_date"]) for b in BL]
pt = [int(b["processing_time"]) for b in BL]
prefs = [b["bay_preferences"] for b in BL]
horizon = a.horizon or (max(due) + max(pt) + 4 * max(pt) + 100)

E = M._ogc_fast_engine(prob)
E.clear_all()

# whole-bay rectangle per bay: feasible_scan_win clamps to the orientation's legal range itself
rects = {j: [0, int(prob["bays"][j]["width"]) + 1, 0, int(prob["bays"][j]["height"]) + 1]
         for j in range(nbay)}

w1, w3 = prob["weights"]["w1"], prob["weights"]["w3"]
order = sorted(range(n), key=lambda i: (due[i], rel[i], -pt[i]))
recs = {}
unplaced = []
t0 = time.time()

for i in order:
    ranked = sorted(range(nbay), key=lambda j: -prefs[i][j])
    smax = max(prefs[i])
    if a.objaware:
        # CONTROL for the best-bay arm.  Same EDD order, same one-block-at-a-time commit, same
        # geometry test -- the ONLY difference is that the bay is chosen by the objective instead
        # of by preference alone.  If this scores like the beam, the constructor is sound and
        # forcing best-bay is what costs; if it scores like the best-bay arm, the constructor is
        # the problem and the best-bay result says nothing about the idea.
        cand = None
        for j in range(nbay):
            pen = w3 * (smax - prefs[i][j])
            if cand is not None and pen >= cand[0]:
                continue          # even at zero tardiness this bay cannot win
            t = rel[i]
            while t + pt[i] <= horizon:
                d = w1 * max(0, t + pt[i] - due[i]) + pen
                if cand is not None and d >= cand[0]:
                    break         # tardiness only grows from here in this bay
                hit = E.feasible_scan_win(i, j, t, t + pt[i], a.step, rects[j])
                if len(hit):
                    cand = (d, j, int(hit[0][0]), int(hit[0][1]), int(hit[0][2]), t)
                    break
                t += 1
        if cand is None:
            unplaced.append(i)
        else:
            _, j, oi, ix, iy, t = cand
            E.add(j, i, oi, float(ix), float(iy), t, t + pt[i])
            recs[i] = {"block_id": i, "bay_id": j, "orient_idx": oi,
                       "x": ix, "y": iy, "entry_time": t, "exit_time": t + pt[i]}
        continue

    bays_to_try = ranked if a.fallback else ranked[:1]
    done = False
    for j in bays_to_try:
        t = rel[i]
        while t + pt[i] <= horizon:
            hit = E.feasible_scan_win(i, j, t, t + pt[i], a.step, rects[j])
            # feasible_scan_win returns an (nrows, 3) array of (orient, ix, iy); row 0 is the first
            # feasible placement found, which is the earliest orientation in the engine's own order
            if len(hit):
                oi, ix, iy = int(hit[0][0]), int(hit[0][1]), int(hit[0][2])
                E.add(j, i, oi, float(ix), float(iy), t, t + pt[i])
                recs[i] = {"block_id": i, "bay_id": j, "orient_idx": oi,
                           "x": ix, "y": iy, "entry_time": t, "exit_time": t + pt[i]}
                done = True
                break
            t += 1
        if done:
            break
    if not done:
        unplaced.append(i)

el = time.time() - t0
sol = M._recs_to_ops(recs, n) if len(recs) == n else None
if sol is None:
    print("P%-3d %-8s BEST-BAY  unplaced=%d/%d  no complete solution  %.1fs"
          % (a.prob, a.tag, len(unplaced), n, el), flush=True)
    sys.exit(0)

obj, chk = M._total(prob, sol)
w = prob["weights"]
z1 = sum(max(0, recs[i]["exit_time"] - due[i]) for i in range(n))
z3 = sum(max(prefs[i]) - prefs[i][recs[i]["bay_id"]] for i in range(n))
best = sum(1 for i in range(n) if recs[i]["bay_id"] == max(range(nbay), key=lambda j: prefs[i][j]))

print("P%-3d %-8s          obj=%-12s feas=%s  Z1=%d Z3=%.0f  best-bay %d/%d  w1Z1=%d w3Z3=%d  %.1fs"
      % (a.prob, a.tag, ("%.0f" % obj) if obj < float("inf") else "inf",
         "y" if (chk and chk.get("feasible")) else "n",
         z1, z3, best, n, w["w1"] * z1, w["w3"] * z3, el), flush=True)
