"""Current numbers for P3, P4 and P5 at their real limits, and where each term stands.

Six hours on these three with targets 80,000 / 22,000,000 / 8,000,000, and the last measured
numbers for them are scattered across a night of logs.  Run every candidate that could plausibly
be the answer once, at the real budget, and write a single table -- plus a JSON per instance so
the headroom analysis has something to read.

Candidates: the beam as it stands (myalg_orig), the beam with cohort weighting (myalg_base,
which is the only beam change that survived the night), and the deployed build.
"""
import importlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402  fixed scorer

LIMIT = {1: 60.0, 2: 120.0, 3: 240.0, 4: 480.0, 5: 600.0, 6: 900.0}
PROB = int(sys.argv[1])
MOD = sys.argv[2]
T = LIMIT[PROB]

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
if MOD == "myalg_pw":            # rebuilt per run so one arm covers the whole prefw sweep
    import subprocess
    subprocess.run(["python3.12", os.path.join(HERE, "harness/mkbase.py"), "0.3", "myalg_pw.py"],
                   cwd=HERE, check=True, capture_output=True)
mod = importlib.import_module(MOD)
t = time.time()
s = mod.algorithm(d, T)
el = time.time() - t
o, c = SC._total(d, s)
fe = SC.check_feasibility(d, s).get("feasible")
print("P%-2d %-12s %4.0fs  obj=%-12d Z1=%-8s Z2=%-6s Z3=%-8s feasible=%s  ran %.0fs"
      % (PROB, MOD, T, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3"), fe, el), flush=True)

path = os.path.join(HERE, "_n/best_%d.json" % PROB)
prev = json.load(open(path)) if os.path.exists(path) else None
if prev is None or o < prev["obj"]:
    json.dump({"obj": o, "z1": c.get("obj1"), "z2": c.get("obj2"), "z3": c.get("obj3"),
               "mod": MOD}, open(path, "w"))
