"""Read w3grid by exchange-rate band, with the control arm kept in view.

w3mul is the beam's bias toward preferred bays.  The prediction under test is directional: raising
it should pay most where preference is worth most -- low w1/w3 -- and least where tardiness swamps
it.  Reading the arms pooled would average opposite predictions against each other, which is the
mistake results/audit/bytype.md documents across four earlier experiments.

The `dn` arm is why this reader prints all arms side by side rather than just the winner.  If dn
also beats base, the effect is perturbation and not preference, and the direction argued from the
weight distributions is wrong.  A reader that highlighted only the best arm would hide that.

Rows whose printed instance contradicts the instance inside their tag are dropped: the notification
stream produced such a line twice this session, once carrying prob_6's objective under prob_1's
header, and reading it would credit one instance with another's result.

    usage: python3.12 harness/w3read.py [logfile]
"""
import json, os, re, statistics, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/w3grid.log")
ROW = re.compile(r"^P(\d+)\s+\[r(\d+)\.([A-Za-z0-9_]+)\.(\d+)\]\s+\d+s\s+obj=(\d+)")
ARMS = ["spread", "up", "dn"]

def rate(p):
    w = json.load(open(os.path.join(HERE, "data/stage2/prob_%d.json" % p)))["weights"]
    return float(w["w1"]) / float(w.get("w3", 1) or 1)

def band(r):
    return "lo <10x" if r < 10 else ("mid 10-50x" if r < 50 else "hi >=50x")

def med(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])

d = {}
for ln in open(LOG, errors="replace"):
    m = ROW.match(ln)
    if m and int(m.group(1)) == int(m.group(4)):
        d.setdefault((int(m.group(4)), m.group(3)), []).append(int(m.group(5)))

probs = [p for p in sorted({q for q, _ in d}, key=rate) if (p, "base") in d]
if not probs:
    sys.exit("no paired rows yet")

print("%-5s %8s %14s %10s %10s %10s" % ("inst", "w1/w3", "base", *ARMS))
per = {a: {} for a in ARMS}
for p in probs:
    b = med(d[(p, "base")])
    cells = []
    for a in ARMS:
        v = d.get((p, a))
        if v:
            dl = 100.0 * (med(v) - b) / b
            per[a].setdefault(band(rate(p)), []).append((p, dl))
            cells.append("%+9.2f%%" % dl)
        else:
            cells.append("%10s" % "-")
    print("P%-4d %7.1fx %14.0f %s %s %s" % (p, rate(p), b, *cells))

print()
for a in ARMS:
    allv = [x for rows in per[a].values() for _, x in rows]
    if not allv:
        continue
    print("  %-7s n=%-2d  median %+6.2f%%  wins %d/%d  worst %+.2f%%"
          % (a, len(allv), med(allv), sum(1 for x in allv if x < 0), len(allv), max(allv)))
    for k in ("lo <10x", "mid 10-50x", "hi >=50x"):
        rows = per[a].get(k)
        if rows:
            print("      %-11s n=%-2d med %+6.2f%%   %s"
                  % (k, len(rows), med([x for _, x in rows]),
                     " ".join("P%d%+.1f" % r for r in rows)))
print()
print("If dn wins alongside spread/up, the direction is not the story and the effect is")
print("perturbation.  If dn loses while the others win, the sign argued from the weights holds.")
