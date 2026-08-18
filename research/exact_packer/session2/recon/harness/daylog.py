"""Pull every experiment's headline numbers out of its own log, for the write-up.

A day with a dozen experiments cannot be reported from memory, and today it especially cannot:
several readings were retracted after more replicates and at least one log line
(rounds r2.R3.20) is contaminated and must not be counted.  So the report is generated from the
logs, and the exclusions are named here in code rather than remembered.

Prints one block per experiment with the numbers that decided it, and says plainly when an
experiment has too few replicates to have decided anything.

    usage: python3.12 harness/daylog.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(HERE, "results/audit")

# Runs excluded from every count, with the reason.  rounds r2.R3.20 returned 1,858,406,007 with
# all four workers scoring inf: it ran inside the window in which myalgorithm.py was being
# edited, between the change that made _worker return (wid, solution) and the change that
# unpacked it, so the caller scored tuples.  Replicates 1 and 3 of the same cell agree at
# 9,087,684.
EXCLUDE = {("rounds", "r2.R3.20"): "ran during a non-atomic edit of myalgorithm.py"}


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def load(path, pat):
    """{(key, prob): [objectives]} from lines tagged [r<rep>.<key>.<prob>]."""
    out = {}
    if not os.path.exists(path):
        return out
    rx = re.compile(r"^P\d+\s+\[r(\d+)\.(%s)\.(\d+)\].*?obj=(\d+)" % pat)
    name = os.path.basename(path).replace(".log", "")
    for ln in open(path, errors="replace"):
        m = rx.match(ln.strip())
        if not m:
            continue
        tag = "r%s.%s.%s" % (m.group(1), m.group(2), m.group(3))
        if (name, tag) in EXCLUDE:
            continue
        out.setdefault((m.group(2), int(m.group(3))), []).append(int(m.group(4)))
    return out


def arms(path, pat, base, others, title):
    d = load(path, pat)
    if not d:
        print("%s: no data\n" % title)
        return
    probs = sorted({p for _, p in d})
    reps = med([len(v) for v in d.values()]) or 0
    rows = {a: [] for a in others}
    n = 0
    for p in probs:
        if not all((a, p) in d for a in (base,) + tuple(others)):
            continue
        n += 1
        b = med(d[(base, p)])
        for a in others:
            rows[a].append(100.0 * (med(d[(a, p)]) - b) / b)
    print("%s  (%d instances, median %.0f replicates each)" % (title, n, reps))
    if reps < 3:
        print("  UNDECIDED -- fewer than three replicates; today three separate readings")
        print("  reversed between one replicate and three.")
    for a in others:
        if rows[a]:
            print("  %-8s vs %-6s  median %+.2f%%   mean %+.2f%%   wins %d of %d"
                  % (a, base, med(rows[a]), sum(rows[a]) / len(rows[a]),
                     sum(1 for x in rows[a] if x < 0), len(rows[a])))
    print()


arms(os.path.join(A, "rounds.log"), r"R\d", "R1", ("R2", "R3"),
     "ROUNDS -- more draws at a shorter budget each")
arms(os.path.join(A, "aimset.log"), r"pair|spread|low", "pair", ("spread", "low"),
     "AIMSET -- fixed beam-aim arrangement across the four workers")
arms(os.path.join(A, "adaptaim.log"), r"fixed|adapt", "fixed", ("adapt",),
     "ADAPTAIM -- each worker moves its own aim from the beam's own report")
arms(os.path.join(A, "abvar.log"), r"old|new", "old", ("new",),
     "ABVAR -- shipped .so vs rebuilt patched .so (CONFOUNDED: different builds)")
arms(os.path.join(A, "samebuild.log"), r"pre|post", "pre", ("post",),
     "SAMEBUILD -- pre- vs post-patch, identical build command")

# Variance, which is what the whole day was about.
d = load(os.path.join(A, "abvar.log"), r"old|new")
if d:
    sp = [100.0 * (max(v) - min(v)) / min(v) for v in d.values() if len(v) > 1 and min(v) > 0]
    if sp:
        print("RUN-TO-RUN SPREAD at 60 s: median %.2f%%, max %.2f%% over %d instance-arms"
              % (med(sp), max(sp), len(sp)))
        print("  (the 3.2-32%% figure quoted earlier came from mixed budgets and does not apply)")
