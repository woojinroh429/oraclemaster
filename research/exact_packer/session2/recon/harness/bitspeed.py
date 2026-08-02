"""Does the free-column bitset change the answer, and does it make the SEARCH faster?

WHY THE SEARCH AND NOT THE BUILD.  Profiling the operator for the first time -- the build had
been profiled repeatedly, the search never -- gave

    build   26,924,021 reads in 50 s
    search  12,791,335,136 reads in 35 s

475x the build's work, in an inner loop nobody had looked at.  Almost all of it is one pattern,
repeated in greedy_extend and again inside try_swap:

    for(int c : colsOfBlock[b]) if(blocked[c]==0) { ...; break; }

a linear scan over every column of a block to find the first UNBLOCKED one.  P3 gives a block
about 404 candidate positions, so the scan is hundreds of loads to answer one question, and the
answer changes only when add_col/rem_col cross a blocked[] counter through zero -- which those
two functions already observe.  The bitset makes them maintain one bit per column, packed 64 to
a word per block, and the scan becomes ctz over a handful of words.

WHY THIS HARNESS AND NOT A FULL RUN.  cranepack's search is a FIXED number of passes (200
restarts, then 60 + 120) truncated by a deadline.  Under a deadline a faster search does not
finish sooner -- it does more work and returns a DIFFERENT placement, so a full run can measure
quality but can never prove the two agree.  Give the pack a budget large enough that the
deadline never binds and both arms run the identical pass sequence; then

    placement identical  <=>  the bitset is a pure representation change
    solve_ms             =    the search time, with nothing else in it

and if either arm reports solve_ms at the budget, the deadline DID bind and that case is thrown
out rather than reported.

CRANEPACK_NOBITS=1 restores the linear scan, so the two arms are one binary and differ only in
which branch runs -- no rebuild between them, and no chance of comparing different compiles.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

# step/nout/nent triples: the tier actually shipped (6,10,1) and the two P3 tiers that cost the
# most search time.  A speedup that only shows on one column count is a measurement, not a lever.
CASES = [("prob_3", 4, 40, 3), ("prob_3", 4, 40, 6), ("prob_3", 6, 10, 1)]
BIG = 900.0   # deadline must not bind; the harness checks that it did not

CHILD = r'''
import json, os, sys, time
sys.path.insert(0, %r)
import myalg_brk as A, bayrepack as R, cranepack as CP
d = json.load(open(os.path.join(%r, "data/hidden/%s.json")))
sol = json.load(open(os.path.join(%r, "results/p3_incumbent.json")))
sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
BIG = %f
_orig = CP.pack
_seen = []
def _spy(*a, **k):
    a = list(a); a[4] = BIG; a = tuple(a)          # index 4 is the ask -- unbind the deadline
    t = time.time(); r = _orig(*a, **k); el = time.time() - t
    _seen.append({"card": float(r[0]), "ncol": r[2], "nedge": r[3],
                  "build_s": float(r[4]) / 1000.0, "solve_s": float(r[5]) / 1000.0,
                  "total_s": el, "place": sorted(r[1])})
    raise SystemExit(0)                            # one call is the measurement
CP.pack = _spy
try:
    R.repack(d, sol, 12.0, A._total, A._build_operations, A._ogc_fast_engine, hard=1e9)
except SystemExit:
    pass
print(json.dumps(_seen[0]) if _seen else "NOCALL")
'''


def run(case, nobits):
    prob, st, no, ne = case
    src = CHILD % (HERE, HERE, prob, HERE, BIG)
    env = dict(os.environ)
    env["CRANEPACK_NOBITS"] = "1" if nobits else "0"
    env["BRK_STEP"], env["BRK_NOUT"], env["BRK_NENT"] = str(st), str(no), str(ne)
    env["OMP_NUM_THREADS"] = "1"        # the arms must not race each other's threads
    out = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True,
                         env=env, cwd=HERE, timeout=7200)
    line = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    if not line or line == "NOCALL":
        sys.stderr.write(out.stderr[-800:] + "\n")
        return None
    return json.loads(line)


print("  %-26s %-8s %-11s %-11s %-8s %s"
      % ("case", "ncol", "scan solve", "bits solve", "speedup", "verdict"))
for c in CASES:
    tag = "%s step=%d nout=%d nent=%d" % c
    a = run(c, nobits=True)
    b = run(c, nobits=False)
    if a is None or b is None:
        print("  %-26s no pack call" % tag)
        continue
    if a["solve_s"] > BIG * 0.98 or b["solve_s"] > BIG * 0.98:
        print("  %-26s deadline bound (%.0fs / %.0fs) -- not comparable"
              % (tag, a["solve_s"], b["solve_s"]))
        continue
    same = (a["ncol"] == b["ncol"] and a["nedge"] == b["nedge"]
            and a["card"] == b["card"] and a["place"] == b["place"])
    print("  %-26s %-8d %-11.1f %-11.1f %-8s %s"
          % (tag, b["ncol"], a["solve_s"], b["solve_s"],
             "%.2fx" % (a["solve_s"] / max(1e-9, b["solve_s"])),
             "IDENTICAL" if same else "DIFFERS -- not a representation change"))
    if not same:
        print("       card %.0f vs %.0f   ncol %d vs %d   edges %d vs %d"
              % (a["card"], b["card"], a["ncol"], b["ncol"], a["nedge"], b["nedge"]))
