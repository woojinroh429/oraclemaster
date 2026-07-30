"""One beam, one axis, fixed budget -- the cleanest place to see whether a scoring change does
anything, without the pipeline's best-of hiding it."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalg_v2 as M
p = int(sys.argv[1]); T = float(sys.argv[2]); tag = sys.argv[3] if len(sys.argv) > 3 else ""
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, 'data/hidden/prob_%d.json' % p)))
cfg = dict(Bmul=1.0, K=4, pos_lam=0.12, order="defer_big", fut_beta=1.0,
           prefw=0.0, w3mul=3.0, mum=0.25, sweep=(1.0, 0.01))
M._OGC_FAST_CACHE.clear()
t = time.time(); s = M._beam_once(d, T, cfg); el = time.time() - t
if s is None:
    print("P%-2d %-12s -> nothing (%.0fs)" % (p, tag)); sys.exit()
o, c = M._total(d, s)
print("P%-2d %-12s obj=%-11d Z1=%-8s Z2=%-6s Z3=%-8s (%.0fs)"
      % (p, tag, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3"), el), flush=True)
