"""Did the entry-sorted sweep change the graph, and how much faster is the build?

THE BUILD IS WHAT COSTS.  On P3's largest tier it is 90 s of a ~95 s call on this host, and it
is the reason the operator can lose a whole instance: when the machine is slower than the
predictor thinks, the chosen tier does not fit, the build refuses it, and brk degrades or
vanishes.  Making the build faster is worth more than making the search smarter, because it
moves the tier the operator can AFFORD.

TWO CHANGES, both exact rather than approximate:

    entry order + break   two columns can only conflict if they are co-present, and once
                          cb.entry >= ca.exit no later b can be either.  ~17% of P3's pairs
                          overlap in time, so the other 83% are never visited instead of being
                          visited and rejected.
    flat filter arrays    block/bbox/entry/exit pulled out of a Col that also owns the layer
                          polygons, so the scan streams 6 sequential arrays instead of 30,000
                          scattered 80-byte structs.

WHAT MAKES THIS CHECKABLE.  Neither touches which pairs CONFLICT, only which pairs are looked
at, so n_edges must come out identical -- and n_edges is returned by pack().  A speedup with a
different edge count is not a speedup, it is a bug, so both are printed side by side and the
edge count is what decides.

Old .so is kept at /tmp/cranepack.old.so; this loads each in a separate process so the two
builds never share an address space.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASES = [("prob_3", 6, 10, 1), ("prob_3", 4, 20, 2), ("prob_3", 4, 40, 6),
         ("prob_6", 6, 10, 1)]

CHILD = r'''
import json, os, sys, time
sys.path.insert(0, %r)
# THE OLD BUILD HAS TO WIN sys.path, and PYTHONPATH does not do that: the insert above puts the
# working directory FIRST, so an env var pointing at the previous .so was silently ignored and
# both arms loaded the same binary.  The giveaway was the "old" column moving 13.6 -> 8.6 s
# between runs of a file that had not changed.  Inserted explicitly, ahead of everything.
_old = os.environ.get("OLD_SO_DIR")
if _old:
    sys.path.insert(0, _old)
import cranepack as _cpcheck
assert (_old is None) == ("/tmp/oldso" not in _cpcheck.__file__), \
    "wrong cranepack loaded: " + _cpcheck.__file__
import myalgorithm as A, bayrepack as R, cranepack as CP
d = json.load(open(os.path.join(%r, "data/hidden/%s.json")))
sol = json.load(open(os.path.join(%r, "results/%s")))
sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
_o = CP.pack; _s = []
def spy(*a, **k):
    a = list(a); a[4] = 0.01; a = tuple(a)      # ask for no search: the BUILD is the measurement
    k["total_s"] = -1.0
    r = _o(*a, **k)
    _s.append({"ncol": r[2], "nedge": int(r[3]), "build_s": float(r[4]) / 1000.0})
    raise SystemExit(0)
CP.pack = spy
try:
    R.repack(d, sol, 12.0, A._total, A._build_operations, A._ogc_fast_engine, hard=1e9)
except SystemExit:
    pass
print(json.dumps(_s[0]) if _s else "NOCALL")
'''

INC = {"prob_3": "p3_incumbent.json", "prob_6": "p6_incumbent.json"}


def run(case, old):
    prob, st, no, ne = case
    src = CHILD % (HERE, HERE, prob, HERE, INC[prob])
    env = dict(os.environ, BRK_STEP=str(st), BRK_NOUT=str(no), BRK_NENT=str(ne))
    cwd = HERE
    if old:
        # a directory whose cranepack is the previous build, ahead of HERE on sys.path
        d = "/tmp/oldso"
        os.makedirs(d, exist_ok=True)
        import shutil
        shutil.copy("/tmp/cranepack.old.so",
                    os.path.join(d, "cranepack.cpython-312-x86_64-linux-gnu.so"))
        env["OLD_SO_DIR"] = d
    else:
        env.pop("OLD_SO_DIR", None)
    out = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True,
                         env=env, cwd=cwd, timeout=3600)
    line = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    if not line or line == "NOCALL":
        sys.stderr.write((out.stderr or "")[-500:] + "\n")
        return None
    return json.loads(line)


print("  %-26s %-8s %-12s %-9s %-9s %-8s %s"
      % ("case", "ncol", "edges", "old build", "new build", "speedup", "verdict"))
for c in CASES:
    tag = "%s s%d n%d e%d" % c
    if not os.path.exists(os.path.join(HERE, "results", INC[c[0]])):
        print("  %-26s no incumbent" % tag)
        continue
    a = run(c, old=True)
    b = run(c, old=False)
    if a is None or b is None:
        print("  %-26s no pack call" % tag)
        continue
    same = (a["ncol"] == b["ncol"] and a["nedge"] == b["nedge"])
    print("  %-26s %-8d %-12d %-9.1f %-9.1f %-8s %s"
          % (tag, b["ncol"], b["nedge"], a["build_s"], b["build_s"],
             "%.2fx" % (a["build_s"] / max(1e-9, b["build_s"])),
             "SAME GRAPH" if same else "EDGES DIFFER -- revert"))
    if not same:
        print("       ncol %d vs %d   edges %d vs %d"
              % (a["ncol"], b["ncol"], a["nedge"], b["nedge"]))
        break
