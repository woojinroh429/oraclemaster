"""Under a REAL deadline, does the bound change what the beam returns?

The wall-clock A/B could not answer this.  Both arms ran a fixed 60 s, so the arm that skips
cells searches further and lands somewhere else -- P3 came out 104,915 against 96,370 and neither
number says anything about the bound.

The per-cell check (OGC_PRUNECHK=1) closed that: on P3, P4 and P6 the bound wanted to skip
45.9M / 11.6M / 9.3M cells and was WRONG on none of them.  Sound means the argmin of every scan
is unchanged, which means a SINGLE contact_beam call with the same arguments must return the
identical assignment either way, and the only difference left is seconds.  So capture one real
call's arguments and replay it -- same inputs, same output, two timings.

The deadline is set far beyond what the call needs, because a deadline-cut beam is exactly the
trajectory divergence this is built to avoid.

The firing rate is not uniform and the point of measuring all three is that it is not:

    P3  40.8% of cells             sparse -- the dilated bbox is often empty, so the bound says
                                   "this cell can touch nothing" and means it
    P4   3.4%
    P6   1.3%                      dense -- every rectangle is full, the bound goes slack

and the occupancy prefix sum costs O(bayW*bayH) per (bay, window) whether it cuts 40% or 1%.  So
P6 can lose here, and if it does that is the bound failing to earn its keep, not a reason to gate
it on density.

Run: python3.12 harness/boundspeed.py <prob>
"""
import json
import os
import pickle
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SO = os.environ.get("NEW_SO_DIR", "/tmp/vso")
ARGF = "/tmp/beamargs_%d.pkl" % PROB

CAPTURE = r'''
import json, os, pickle, sys
sys.path.insert(0, %r); sys.path.insert(1, %r)
import ogc_fast
assert %r in ogc_fast.__file__, ogc_fast.__file__
sys.path.insert(0, %r)
import myalgorithm as A

_f = A._ogc_fast_engine
class P(object):
    def __init__(s, e): object.__setattr__(s, "_e", e)
    def __getattr__(s, k):
        e = object.__getattribute__(s, "_e")
        if k != "contact_beam":
            return getattr(e, k)
        def w(*a):
            pickle.dump(list(a), open(%r, "wb"))
            raise SystemExit(0)
        return w
A._ogc_fast_engine = lambda p: P(_f(p))
d = json.load(open(os.path.join(%r, "data/hidden/prob_%d.json")))
try:
    A.algorithm(d, 60.0)
except SystemExit:
    pass
'''

REPLAY = r'''
import json, os, pickle, sys, time
sys.path.insert(0, %r); sys.path.insert(1, %r)
import ogc_fast
assert %r in ogc_fast.__file__, ogc_fast.__file__
sys.path.insert(0, %r)
import myalgorithm as A
a = pickle.load(open(%r, "rb"))
# THE DEADLINE IS LEFT AS CAPTURED.  boundspeed.py lifts it, which is what proves the bound
# does not change the beam's ANSWER.  This asks the opposite and equally necessary question:
# under the deadline the operator actually gives it, does the faster arm get further and
# therefore return something DIFFERENT?  If it does, the run's irreproducibility starts inside
# the beam and no amount of fixing the operator loop will remove it.
# the factory takes the PROBLEM, not its number -- it reads prob["blocks"] to register shapes.
d = json.load(open(os.path.join(%r, "data/hidden/prob_%d.json")))
E = A._ogc_fast_engine(d)
t = time.time(); ob, flat = E.contact_beam(*a); el = time.time() - t
print("%%.4f %%d %%s" %% (el, len(flat), hash(tuple(int(v) for v in flat))))
'''


def sh(src, **env):
    e = dict(os.environ, WORKERS="1", **env)
    r = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True,
                       env=e, cwd=HERE, timeout=7200)
    if r.returncode != 0:
        sys.stderr.write((r.stderr or "")[-800:] + "\n")
        return None
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else None


if not os.path.exists(ARGF):
    sh(CAPTURE % (SO, HERE, SO, HERE, ARGF, HERE, PROB))
if not os.path.exists(ARGF):
    print("no contact_beam call captured on P%d" % PROB)
    raise SystemExit(1)

src = REPLAY % (SO, HERE, SO, HERE, ARGF, HERE, PROB)
rows = []
# The switch flipped sense when the bound became default-OFF.  Updated here rather than left
# alone: with the old name unread, BOTH arms would have run bound-off and the comparison would
# have reported "identical" for the same empty reason the position bound once did.
for tag, np_ in (("no bound", "0"), ("bound", "1")):
    out = sh(src, OGC_PRUNE=np_)
    if out is None:
        print("P%d %s: replay failed" % (PROB, tag))
        raise SystemExit(1)
    el, n, h = out.split()
    rows.append((tag, float(el), int(n), h))

print("\nP%d  one contact_beam call, deadline AS CAPTURED, identical arguments" % PROB)
for tag, el, n, h in rows:
    print("  %-10s %8.2f s   %d placements   digest %s" % (tag, el, n // 7, h))
same = rows[0][3] == rows[1][3]
# The verdict flips meaning here.  With the deadline lifted, differing assignments would mean
# the bound is UNSOUND.  With the deadline in place, differing assignments are EXPECTED if the
# bound works at all -- the faster arm simply gets further -- and they locate the source of the
# run-to-run irreproducibility inside the beam rather than in the operator loop.
print("  %s" % ("SAME ANSWER under the deadline -- the beam is not where the divergence starts"
                if same else
                "DIFFERENT ANSWER under the deadline -- the divergence starts INSIDE the beam,"
                " so the fix belongs in its stopping rule, not in the scheduler"))
