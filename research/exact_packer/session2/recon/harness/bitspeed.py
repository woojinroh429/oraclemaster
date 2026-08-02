"""Is the free-column bitset the SAME search, and how much faster?

WHY THE SEARCH.  Profiling the operator for the first time -- the build had been profiled
repeatedly, the search never -- gave

    build   26,924,021 reads in 50 s
    search  12,791,335,136 reads in 35 s

475x the build's work, in an inner loop nobody had looked at.  Nearly all of it is one pattern,
in greedy_extend and again inside try_swap:

    for(int c : colsOfBlock[b]) if(blocked[c]==0) { ...; break; }

a linear scan over a block's ~404 candidate positions to answer "which column of this block is
free".  blocked[] only crosses zero inside add_col/rem_col, so those two can maintain one bit
per column, 64 to a word per block, and the scan becomes ctz over about seven words.  Nothing
about WHICH column is chosen changes -- still the first free one in the same order -- so the
placement must come out identical or the change is wrong.

WHY THE FIRST VERSION OF THIS HARNESS FAILED, and what replaced it.  cranepack's search is a
fixed pass sequence TRUNCATED BY A DEADLINE.  Under a deadline a faster search does not finish
sooner, it does more passes and returns a different placement -- so "faster" and "different"
cannot be told apart.  The first attempt unbound the deadline instead, which was worse: the ILS
loop exits only on the clock or on best==nblk, and at 31,000 columns every block never does get
seated, so a single arm ran 22 minutes without finishing and the run was killed.

The fix is to bound ITERATIONS, not time.  max_iters (default -1, shipped behaviour untouched)
makes both arms perform exactly the same number of passes whatever their speed, so

    placement identical  <=>  the bitset is a pure representation change
    solve_ms             =    the same work, timed twice

Small caps first: if the two arms already disagree after twenty passes there is no point paying
for two hundred.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

# (step, nout, nent, iterations).  Rising column counts and rising pass counts, so a
# disagreement is caught at the cheapest size that can show it.
CASES = [
    ("prob_3", 6, 10, 1, 20),
    ("prob_3", 6, 10, 1, 200),
    ("prob_3", 4, 20, 2, 60),
    ("prob_3", 4, 40, 6, 60),
    ("prob_6", 6, 10, 1, 40),
]

CHILD = r'''
import json, os, sys, time
sys.path.insert(0, %r)
import myalgorithm as A, bayrepack as R, cranepack as CP
d = json.load(open(os.path.join(%r, "data/hidden/%s.json")))
sol = json.load(open(os.path.join(%r, "results/%s")))
sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
MAXIT = %d
_orig = CP.pack
_seen = []
def _spy(*a, **k):
    a = list(a); a[4] = 1e9; a = tuple(a)      # the clock must never be the thing that stops it
    k["total_s"] = -1.0
    k["max_iters"] = MAXIT
    t = time.time(); r = _orig(*a, **k); el = time.time() - t
    _seen.append({"card": float(r[0]), "ncol": r[2], "nedge": r[3],
                  "build_s": float(r[4]) / 1000.0, "solve_s": float(r[5]) / 1000.0,
                  "wall": el, "place": sorted(r[1])})
    raise SystemExit(0)                         # one call is the measurement
CP.pack = _spy
try:
    R.repack(d, sol, 12.0, A._total, A._build_operations, A._ogc_fast_engine, hard=1e9)
except SystemExit:
    pass
print(json.dumps(_seen[0]) if _seen else "NOCALL")
'''


def run(case, nobits, incumbent):
    prob, st, no, ne, mx = case
    src = CHILD % (HERE, HERE, prob, HERE, incumbent, mx)
    env = dict(os.environ)
    env["CRANEPACK_NOBITS"] = "1" if nobits else "0"
    env["BRK_STEP"], env["BRK_NOUT"], env["BRK_NENT"] = str(st), str(no), str(ne)
    out = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True,
                         env=env, cwd=HERE, timeout=3600)
    line = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    if not line or line == "NOCALL":
        sys.stderr.write((out.stderr or "")[-600:] + "\n")
        return None
    return json.loads(line)


INCUMBENT = {"prob_3": "p3_incumbent.json", "prob_6": "p6_incumbent.json"}

print("  %-28s %-8s %-10s %-10s %-8s %s"
      % ("case", "ncol", "scan", "bits", "speedup", "verdict"))
for c in CASES:
    tag = "%s s%d n%d e%d x%d" % c
    inc = INCUMBENT.get(c[0])
    if not inc or not os.path.exists(os.path.join(HERE, "results", inc)):
        print("  %-28s no incumbent to repack" % tag)
        continue
    a = run(c, True, inc)
    b = run(c, False, inc)
    if a is None or b is None:
        print("  %-28s no pack call" % tag)
        continue
    same = (a["ncol"] == b["ncol"] and a["nedge"] == b["nedge"]
            and a["card"] == b["card"] and a["place"] == b["place"])
    print("  %-28s %-8d %-10.2f %-10.2f %-8s %s"
          % (tag, b["ncol"], a["solve_s"], b["solve_s"],
             "%.2fx" % (a["solve_s"] / max(1e-9, b["solve_s"])),
             "IDENTICAL" if same else "DIFFERS -- revert"))
    if not same:
        print("       card %.0f vs %.0f   ncol %d vs %d   edges %d vs %d"
              % (a["card"], b["card"], a["ncol"], b["ncol"], a["nedge"], b["nedge"]))
        break
