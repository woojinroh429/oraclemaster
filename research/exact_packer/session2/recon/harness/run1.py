"""One run, exactly as the grader calls it.  Lives in the repo, not /tmp -- container restarts
have taken the throwaway copies twice and killed a night's queue each time."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib
mod = importlib.import_module(sys.argv[1])
p = int(sys.argv[2]); T = float(sys.argv[3]); tag = sys.argv[4] if len(sys.argv) > 4 else ""
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, 'data/hidden/prob_%d.json' % p)))
t = time.time(); s = mod.algorithm(d, T); el = time.time() - t
o, c = mod._total(d, s)
print("P%-2d %-12s %5.0fs  obj=%-11d Z1=%-8s Z2=%-6s Z3=%-8s  ran %.0fs"
      % (p, tag or sys.argv[1], T, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3"), el),
      flush=True)
