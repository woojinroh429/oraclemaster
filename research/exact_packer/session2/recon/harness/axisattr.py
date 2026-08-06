"""Which worker is carrying the run, and which one never wins?

The four workers land a median of 29% apart and the run keeps only their minimum, so up to three
of four cores can be producing nothing that survives.  That is not automatically waste -- a
portfolio is paid for by the draws that win, and a worker that loses on this instance may be the
one that carries the next.  It becomes waste only if the SAME worker loses everywhere.

wid fixes what makes a worker different, so the question is answerable by counting:

    aim     _aims[wid % len(_aims)], default "0.90,0.10" -- even workers run the high beam aim,
            odd workers the low one.  The 2:2 split was chosen because 0.10 measured -24.3% to
            -11.9% on 250-300 block instances and +25.09% on prob_1, so both had to be in the
            portfolio.  Whether that still holds at 60 s is exactly what this counts.
    axes    _AXES[(wid + i) % len(_AXES)] -- a rotation of six configs, so each wid starts its
            bandit from a different one.
    seed    Random(1234 + wid).

Per instance it reports how often each wid supplied the minimum, and how far each sits above it
on average.  A wid that never wins AND sits far above is a core doing nothing; a wid that wins
rarely but by a lot is the portfolio working as designed and must not be removed.

REQUIRES LOGS WRITTEN AFTER THE wid-ORDER FIX (myalgorithm da48660).  Before that _pool_round
returned results in completion order, so column position did not mean wid and every number this
script prints would be attributed to the wrong worker.  Passing an older log is silently wrong,
so the caller must pass logs it knows are new -- there is no marker in the file to check.

    usage: python3.12 harness/axisattr.py <logfile> [logfile ...]
"""
import os
import re
import sys

TAG = re.compile(r"^#\s*\[(\S+)\]")
PID = re.compile(r"\.(\d+)$")     # TAG already stripped the brackets; requiring ']' here matched
                                  # nothing and the script reported "no usable WSTAT rows", which
                                  # reads as missing data rather than a broken regex.
WST = re.compile(r"^WSTAT round=(\d+) n=(\d+)\s+(.*?)\s+spread=")

AIMS = os.environ.get("OGC_AIMSET", "0.90,0.10").split(",")

wins, above, cur = {}, {}, None
for path in sys.argv[1:]:
    if not os.path.exists(path):
        print("missing: %s" % path)
        continue
    for ln in open(path, errors="replace"):
        ln = ln.strip()
        m = TAG.match(ln)
        if m:
            q = PID.search(m.group(1))
            cur = int(q.group(1)) if q else None
            continue
        m = WST.match(ln)
        if not m or cur is None:
            continue
        raw = m.group(3).split()
        vals = []
        for v in raw:
            try:
                vals.append(float(v))
            except ValueError:
                vals.append(None)                      # '-' for a worker that never returned
        good = [v for v in vals if v is not None and v == v and v < float("inf")]
        if len(good) < 2:
            continue
        lo = min(good)
        if lo <= 0:
            continue
        for i, v in enumerate(vals):
            if v is None or v != v or v >= float("inf"):
                continue
            wins.setdefault((cur, i), [0, 0])
            wins[(cur, i)][1] += 1
            if v == lo:
                wins[(cur, i)][0] += 1
            above.setdefault((cur, i), []).append(100.0 * (v - lo) / lo)

if not wins:
    sys.exit("no usable WSTAT rows -- pass logs written with OGC_WSTAT=1 after da48660")


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


probs = sorted({p for p, _ in wins})
nw = 1 + max(i for _, i in wins)
print("%-6s %-5s %-6s %8s %10s   %s" % ("inst", "wid", "aim", "wins", "above min", ""))
never = {}
for p in probs:
    for i in range(nw):
        if (p, i) not in wins:
            continue
        w, n = wins[(p, i)]
        print("P%-5d %-5d %-6s %4d/%-3d %9.2f%%   %s"
              % (p, i, AIMS[i % len(AIMS)].strip(), w, n, med(above[(p, i)]),
                 "" if w else "never wins here"))
        never.setdefault(i, [0, 0])
        never[i][0] += w
        never[i][1] += n
    print()

print("across all instances:")
for i in sorted(never):
    w, n = never[i]
    allab = [x for (p, j), xs in above.items() if j == i for x in xs]
    print("  wid %d  aim %-5s  supplied the minimum %d of %d rounds (%.0f%%),"
          "  median %.2f%% above it"
          % (i, AIMS[i % len(AIMS)].strip(), w, n, 100.0 * w / max(1, n), med(allab)))
print("\nA wid that never wins anywhere is a core producing nothing the answer keeps.")
print("A wid that wins rarely but by a wide margin is the portfolio doing its job -- leave it.")
