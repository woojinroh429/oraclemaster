"""THE SEED GENERATOR PRODUCTION ACTUALLY USES, MEASURED WITHOUT A CLOCK.

beam1.py calls `_contact_beam` directly with step=1.  Production calls `_beam_once`, which
    - splits the budget between a FINE rung (step 1) and a COARSE rung (step 2) held in reserve,
    - redraws the block order on repeat visits when the axis carries dk > 1,
    - passes `share`.
So beam1 ranks the fine rung in isolation, and the axis ordering it produces is a statement about
a search that never runs.  That is why its axis-2 numbers (684,687 at work 3,000) sit on the wrong
side of production's axis-2 seeds (587,906): different searches.

This calls `_beam_once` itself, so the two-rung structure, the reserve and the order redraw are
all in play, and OGC_WORKCAP still removes the clock from the beam's stop test and both width
controllers.  The budget passed is deliberately enormous -- work, not seconds, is what stops it.

Determinism is VERIFIED, not assumed: the placement digest is printed, so two runs of one
configuration are identical only if the digest matches.  If _beam_once turns out NOT to be
reproducible under WORKCAP -- the reserve split reads `budget`, which is seconds -- the digests
will say so, and that is itself the finding: it would mean the production seed generator cannot be
measured without noise and every axis comparison has to go back to replicates.

    usage: python3.12 harness/beamprod.py <prob> [--work N] [--axis k] [--reps n] [--data DIR]
"""
import argparse, hashlib, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ap = argparse.ArgumentParser()
ap.add_argument("prob", type=int)
ap.add_argument("--work", type=float, default=3000.0)
ap.add_argument("--axis", type=int, default=0)
ap.add_argument("--reps", type=int, default=1, help="repeat to verify the digest is stable")
ap.add_argument("--budget", type=float, default=1e9, help="seconds; work is what should stop it")
ap.add_argument("--data", default="data/stage2")
ap.add_argument("--tag", default="")
a = ap.parse_args()

os.environ["OGC_WORKCAP"] = str(a.work)
import myalgorithm as M
import json

prob = json.load(open(os.path.join(a.data, "prob_%d.json" % a.prob)))
cfg = M._AXES[a.axis % len(M._AXES)]
n = len(prob["blocks"])

for rep in range(a.reps):
    t0 = time.time()
    sol = M._beam_once(prob, a.budget, cfg)
    el = time.time() - t0
    obj, chk = (M._total(prob, sol) if sol is not None else (float("inf"), None))
    dig = "-"
    if sol is not None:
        h = hashlib.sha256()
        for t in sorted((sol or {}).get("operations", {}), key=lambda x: int(x)):
            for op in sol["operations"][t]:
                h.update(repr((t, op.get("block_id"), op.get("type"), op.get("bay_id"),
                               op.get("x"), op.get("y"), op.get("orientation"))).encode())
        dig = h.hexdigest()[:16]
    print("P%-3d %-14s work=%-8.0f axis=%d rep=%d  obj=%-12s feas=%s  %6.1fs  digest=%s"
          % (a.prob, a.tag or "beamprod", a.work, a.axis, rep,
             ("%.0f" % obj) if obj < float("inf") else "inf",
             "y" if (chk and chk.get("feasible")) else "n", el, dig), flush=True)
