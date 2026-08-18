"""What does the deployed build's ultra-dense construction score on its own?

P6 is the only hidden instance in the ultra band (demand ratio 1.137; P5 is 0.730 and the rest
are below 0.35), and it is the only one where the deployed build switches the contact beam OFF
entirely.  What it runs instead is not a search: one worker spends almost the whole budget
completing a single greedy construction, bigleft at step=1, with ALNS explicitly disabled
because it measured net-negative there.

That is the opposite of what the rebuild does on P6 -- many shallow partial states from a beam
-- and the rebuild is 6.4% behind on exactly this instance.  So the question worth answering
before porting anything is the simple one: standalone, given the same budget, what does that
construction score?

Mirrors the dedicated worker at myalgorithm.py:4502-4520, including the _CPP_ENGINE_MODE it
sets, so the number is the construction's and not a harness artefact.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import myalg_legacy as A          # noqa: E402
import myalg_orig as SC          # noqa: E402  fixed scorer; myalgorithm has no _total

PROB = int(sys.argv[1])
SECS = float(sys.argv[2])
MODE = sys.argv[3] if len(sys.argv) > 3 else "bigleft"
STEP = int(sys.argv[4]) if len(sys.argv) > 4 else 1
# The construction takes a dispatch ORDER and a small-block threshold, and neither has been
# looked at for P6.  The deployed build's own note says "recon had only rank", and its ablation
# says the small-block rule (sx) is worth 4.2% -- more than the sweep direction's 2% -- so the
# threshold that decides which blocks get that rule is the untuned knob with the most attached
# to it.
ORDER = sys.argv[5] if len(sys.argv) > 5 else "rank"
THR   = float(sys.argv[6]) if len(sys.argv) > 6 else 0.60

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
n = len(d["blocks"])

saved = A._CPP_ENGINE_MODE
A._CPP_ENGINE_MODE = A.HAVE_OGC_FAST
t = time.time()
try:
    recs = A._smallright_construct(d, max(1.0, SECS - 2.0), small_thresh=THR,
                                   step=STEP, mode=MODE, order=ORDER)
finally:
    A._CPP_ENGINE_MODE = saved
el = time.time() - t

if not recs or len(recs) != n:
    print("P%-2d %-10s ord=%-7s thr=%.2f INCOMPLETE (%s of %d blocks placed) in %.0fs"
          % (PROB, MODE, ORDER, THR, len(recs) if recs else 0, n, el), flush=True)
    sys.exit()

sol = A._build_operations([recs[b] for b in range(n)])
chk = A.check_feasibility(d, sol)
o, c = SC._total(d, sol)
print("P%-2d %-10s ord=%-7s thr=%.2f obj=%-11d Z1=%-8s Z2=%-6s Z3=%-8s feasible=%s  built in %.0fs"
      % (PROB, MODE, ORDER, THR, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3"),
         chk.get("feasible"), el), flush=True)
