"""One run, exactly as the grader calls it.  Lives in the repo, not /tmp -- container restarts
have taken the throwaway copies twice and killed a night's queue each time."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib

# THE C++ EXTENSIONS ARE NOT OPTIONAL, AND THE FALLBACK IS SILENT.
#
# The container came back with /usr/local/bin/python3 = 3.11 where it had been 3.12.  The .so
# files carry the interpreter's ABI tag in their names, so under 3.11 ogc_fast and cranepack
# simply do not exist as far as the import system is concerned; myalgorithm caught the
# ImportError, took the pure-Python path, and returned a legal solution.  On prob_36 that
# solution scored 4,023,023,953 against the 88,211,571 the same code had returned an hour
# earlier -- 45x worse, feasible, and printed in the ordinary format with no warning anywhere.
# It cost an A/B study before the number was questioned.
#
# So refuse to run rather than measure the fallback by accident.  Anything comparing against a
# log in results/ must be on the same engine those logs were made with.
for _m in ("ogc_fast", "cranepack"):
    try:
        importlib.import_module(_m)
    except ImportError as _e:
        sys.exit("run1: %s will not import under %s (%s).\n"
                 "      The .so files are ABI-tagged; build them for this interpreter or run\n"
                 "      the one they were built for.  Refusing to measure the Python fallback."
                 % (_m, sys.version.split()[0], _e))

# AND THE PURE-PYTHON DEPENDENCIES, FOR THE SAME REASON.
#
# The container came back from a restart with python3.12's site-packages emptied -- shapely, numpy
# and ortools all gone, while python3.11 kept its copies and `pip` pointed at 3.11.  keepalive
# dutifully relaunched the queue, every cell raised ModuleNotFoundError inside utils, and the
# harness recorded 64 "HANG-OR-CRASH" lines that look exactly like a real hang.  Worse, the
# resume logic then treats a recorded crash as a finished cell, so those runs would never have
# been retried.
#
# Fail here instead, with the fix in the message.
for _d in ("shapely", "numpy"):
    try:
        importlib.import_module(_d)
    except ImportError as _e:
        sys.exit("run1: %s is missing under %s (%s).\n"
                 "      python3.12 -m pip install --break-system-packages shapely numpy ortools\n"
                 "      (pip alone targets 3.11 on this image and will not fix 3.12.)"
                 % (_d, sys.version.split()[0], _e))

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
print("P%-2d %-12s %5.0fs  obj=%-11d Z1=%-8s Z2=%-6s Z3=%-8s  feas=%-3s ran %.0fs  py%s"
      % (p, tag or sys.argv[1], T, int(o), c.get("obj1") if c else "-",
         c.get("obj2") if c else "-", c.get("obj3") if c else "-", _feas, el,
         ".".join(str(v) for v in sys.version_info[:2])),
      flush=True)
