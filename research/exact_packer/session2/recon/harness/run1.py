"""One run, exactly as the grader calls it.  Lives in the repo, not /tmp -- container restarts
have taken the throwaway copies twice and killed a night's queue each time."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib
mod = importlib.import_module(sys.argv[1])
p = int(sys.argv[2]); T = float(sys.argv[3]); tag = sys.argv[4] if len(sys.argv) > 4 else ""
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# data/hidden by default, so every existing harness and every log in results/ keeps its meaning.
# --data <dir> points at the 40 training instances, which the technical report needs and which
# had never been on disk in this container until they were supplied.
_dd = 'data/hidden'
if '--data' in sys.argv:
    _dd = sys.argv[sys.argv.index('--data') + 1]
d = json.load(open(os.path.join(here, _dd, 'prob_%d.json' % p)))
t = time.time(); s = mod.algorithm(d, T); el = time.time() - t
# Score with a fixed scorer, not the module under test.  The deployed build has no _total,
# so a 900s P6 run finished and then threw the result away at the last line.
try:
    o, c = mod._total(d, s)
except AttributeError:
    import myalg_orig as _SC
    o, c = _SC._total(d, s)
# FEAS is printed, not assumed.  _total returns inf for an infeasible solution, which reads as
# a huge objective and could be mistaken for a bad-but-legal run; and arms that screen the
# objective for speed need the geometric verdict stated out loud rather than inferred.
_feas = "?" if c is None else ("y" if c.get("feasible") else "NO")
print("P%-2d %-12s %5.0fs  obj=%-11d Z1=%-8s Z2=%-6s Z3=%-8s  feas=%-3s ran %.0fs"
      % (p, tag or sys.argv[1], T, int(o), c.get("obj1") if c else "-",
         c.get("obj2") if c else "-", c.get("obj3") if c else "-", _feas, el),
      flush=True)
