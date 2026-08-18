"""Why does P3 concede 546 units of preference on a yard that is a third full?

P3's demand ratio is 0.327 and its Z1 is already 0, so its whole objective is preference (78%)
and balance (22%).  We score 97,570, the deployed build 90,545, and competitors ranked well below
us are reported at 70,000-84,000.  The capacity bound on Z3 is 134 against our 546, so the room
is there -- the question is what is actually stopping each concession.

Raising prefw did not answer it: 0.5 changed literally nothing (contact dominates the argmin at
that scale) and 2 made it WORSE, Z3 rising 546 -> 622.  So this counts instead of theorising.

For every block that did not get its top-preference bay, ask the engine directly, with that block
lifted out of the timeline and everything else left where it is:

  now       could it have gone into its preferred bay at the entry time it actually used?
            If yes, nothing physical stopped it -- the beam simply scored something else higher.
  free      is there ANY entry time in [release, due - processing] where the preferred bay takes
            it?  That window costs no tardiness at all, so anything found here is Z3 recoverable
            for free -- and at w1 17778 against w3 150, a concession that needs even one unit of
            tardiness to undo is never worth it.
  blocked   nowhere in that window fits: the preferred bay is genuinely unavailable whenever the
            block could use it, and this concession is forced.

The split says which problem P3 actually has.  Mostly "now" means the scorer is the whole story.
Mostly "free" means the beam is choosing entry times badly on an instance with slack to spare.
Mostly "blocked" means the capacity bound is loose and 546 is closer to forced than it looks.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as M          # noqa: E402
import importlib                # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
MOD = sys.argv[2] if len(sys.argv) > 2 else "myalg_base"
LIMIT = {3: 240.0, 4: 480.0, 5: 600.0, 6: 900.0}
T = float(sys.argv[3]) if len(sys.argv) > 3 else LIMIT[PROB]

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B = d["blocks"]
n = len(B)
m = len(d["bays"])

sol = importlib.import_module(MOD).algorithm(d, T)
o, c = M._total(d, sol)
print("P%d %s  obj=%d  Z1=%s Z2=%s Z3=%s" % (PROB, MOD, int(o), c.get("obj1"), c.get("obj2"),
                                             c.get("obj3")), flush=True)

ent, ext = {}, {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            ent[op["block_id"]] = (op["bay_id"], op["orient_idx"], int(op["x"]), int(op["y"]), int(t))
        else:
            ext[op["block_id"]] = int(t)

pref = [B[b]["bay_preferences"] for b in range(n)]
want = [max(range(m), key=lambda j: pref[b][j]) for b in range(n)]
penal = [b for b in range(n) if ent[b][0] != want[b]]
lost = sum(max(pref[b]) - pref[b][ent[b][0]] for b in penal)
print("   %d of %d blocks are not in their preferred bay, costing %.0f of Z3"
      % (len(penal), n, lost), flush=True)


def fits(E, b, bay, en, ex):
    """Any feasible (orient, x, y) for b in bay over [en, ex), against the current timeline.

    feasible_scan, not feasible_scan_win.  The windowed variant restricts the scan to a list of
    rectangles and loops `for r in 0..R`, so an EMPTY rect list scans nothing and returns an empty
    array for every input -- which is what the first cut of this file passed.  Every block came
    back "blocked" because the question was never asked.
    """
    try:
        out = E.feasible_scan(int(b), [int(bay)], int(en), int(ex), 1)
        return len(out) > 0
    except Exception:
        return False


now_ok = free_ok = blocked = 0
free_gain = 0.0
now_gain = 0.0
for b in penal:
    E = M._ogc_fast_engine(d)
    E.clear_all()
    for q in range(n):                       # everything except b, exactly where it sits
        if q == b:
            continue
        bay, oi, x, y, t = ent[q]
        E.add(int(bay), int(q), int(oi), float(x), float(y), int(t), int(ext[q]))
    gain = max(pref[b]) - pref[b][ent[b][0]]
    en0 = ent[b][4]
    pt = B[b]["processing_time"]
    if fits(E, b, want[b], en0, en0 + pt):
        now_ok += 1
        now_gain += gain
        continue
    lo = B[b]["release_time"]
    hi = B[b]["due_date"] - pt              # entering later than this would create tardiness
    found = False
    if hi >= lo:
        span = hi - lo
        for t in sorted({lo, hi} | {lo + span * i // 8 for i in range(9)}):
            if fits(E, b, want[b], t, t + pt):
                found = True
                break
    if found:
        free_ok += 1
        free_gain += gain
    else:
        blocked += 1

print("   now      %3d blocks (%.0f of Z3)  preferred bay was free at the time actually used --"
      " nothing physical stopped it" % (now_ok, now_gain))
print("   free     %3d blocks (%.0f of Z3)  fits at some entry time that costs no tardiness"
      % (free_ok, free_gain))
print("   blocked  %3d blocks              preferred bay never available in the tardiness-free"
      " window" % blocked)
print("   -> %.0f of %.0f conceded Z3 is recoverable without touching Z1, worth %.0f of objective"
      % (now_gain + free_gain, lost, (now_gain + free_gain) * d["weights"]["w3"]))
