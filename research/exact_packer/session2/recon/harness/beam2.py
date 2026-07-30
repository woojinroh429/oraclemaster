"""One beam, one module, one cohort floor.

The pipeline's best-of hides a scoring change behind whichever axis happened to win, so the
floor sweep has to run where the change actually acts: a single beam on a single axis, with
everything else held fixed.

Note on the floor: COHORT_on() is coh_floor > 0.0, so 0.0 means the weighting is OFF, not
"pure overlap ratio".  Pure overlap is approached from above -- 0.05 is within 5% of it -- and
1.0 collapses the weight back to a flat 1.0, i.e. plain contact with the code path still live.
So the sweep spans plain (1.0) to nearly-pure (0.05), with 0.0 as the feature-off control.
"""
import importlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

M = importlib.import_module(sys.argv[1])
p = int(sys.argv[2])
T = float(sys.argv[3])
coh = float(sys.argv[4])
tag = sys.argv[5] if len(sys.argv) > 5 else ("coh%.2f" % coh)

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % p)))
cfg = dict(Bmul=1.0, K=4, pos_lam=0.12, order="defer_big", fut_beta=1.0,
           prefw=0.0, w3mul=3.0, cohort=coh)
M._OGC_FAST_CACHE.clear()
t = time.time()
s = M._beam_once(d, T, cfg)
el = time.time() - t
if s is None:
    print("P%-2d %-10s -> nothing (%.0fs)" % (p, tag, el), flush=True)
    sys.exit()
o, c = M._total(d, s)
print("P%-2d %-10s floor=%-5.2f obj=%-11d Z1=%-8s Z2=%-6s Z3=%-8s (%.0fs)"
      % (p, tag, coh, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3"), el), flush=True)
