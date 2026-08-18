"""Run ONE of the checked-out submitted builds, exactly as the grader would have loaded it.

run1.py cannot do this: it imports `myalgorithm` off the recon directory, and the whole point
here is that the module, both C++ extensions, bayrepack and utils must ALL come from the same
submitted package.  So the build directory goes on the front of sys.path and the import of
ogc_fast/cranepack is checked BEFORE the module is loaded -- myalgorithm catches ImportError and
falls back to pure Python silently, which has already cost this project one A/B study.

The scorer is the module's own _total, which is byte-identical across the two builds (checked:
sha b373be48f8117fa8 in both), so the arms are scored by the same function and the comparison is
not confounded by it.

    usage: python3.12 harness/subrun.py <builddir> <prob> <seconds> <tag> [--data dir]
"""
import sys, os, json, time, importlib

BUILD = os.path.abspath(sys.argv[1])
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BUILD)

for _m in ("ogc_fast", "cranepack"):
    _mod = importlib.import_module(_m)
    _f = getattr(_mod, "__file__", "") or ""
    if not _f.startswith(BUILD):
        sys.exit("subrun: %s came from %s, not the build under test" % (_m, _f))

mod = importlib.import_module("myalgorithm")
if not (getattr(mod, "__file__", "") or "").startswith(BUILD):
    sys.exit("subrun: myalgorithm came from %s" % mod.__file__)

p = int(sys.argv[2]); T = float(sys.argv[3]); tag = sys.argv[4] if len(sys.argv) > 4 else ""
_dd = "data/stage2"
if "--data" in sys.argv:
    _dd = sys.argv[sys.argv.index("--data") + 1]
d = json.load(open(os.path.join(HERE, _dd, "prob_%d.json" % p)))
t = time.time(); s = mod.algorithm(d, T); el = time.time() - t
o, c = mod._total(d, s)
_feas = "?" if c is None else ("y" if c.get("feasible") else "NO")
print("P%-2d %-14s %5.0fs  obj=%-11d Z1=%-8s Z2=%-6s Z3=%-8s  feas=%-3s ran %.0fs  %s"
      % (p, tag or os.path.basename(BUILD), T, int(o), c.get("obj1") if c else "-",
         c.get("obj2") if c else "-", c.get("obj3") if c else "-", _feas, el,
         open(os.path.join(BUILD, "SHA")).read().strip()),
      flush=True)
