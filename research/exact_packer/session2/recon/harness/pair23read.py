"""Read pair23: is the third submission better than the second, and by how much?

Paired on the instance, because the instance-to-instance range is four orders of magnitude and
an unpaired mean is decided entirely by the largest instance.  Reports the sign count and the
median relative change, which are the two statistics the split-aim and per-seat studies used, so
this number is directly comparable to the -3.44% and -0.74% already in the report.

Also prints the eight-instance question explicitly: how often a random eight of these forty would
have shown the improvement, given the per-instance changes actually measured.  That is the whole
reason for running this -- the submitted totals moved -0.0% and the claim under test is that
eight draws cannot see the effect.

    usage: python3.12 harness/pair23read.py [logfile]
"""
import os, re, sys, itertools

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/pair23.log")
OBJ = re.compile(r"^P(\d+)\s+\[r(\d+)\.(sub\d)\.(\d+)\].*?obj=(\d+)")
HANG = re.compile(r"^P(\d+)\s+\[r(\d+)\.(sub\d)\.(\d+)\]\s+HANG")

d, hangs = {}, []
for ln in open(LOG, errors="replace"):
    ln = ln.strip()
    m = OBJ.match(ln)
    if m:
        d.setdefault((int(m.group(4)), m.group(3)), []).append(int(m.group(5)))
        continue
    m = HANG.match(ln)
    if m:
        hangs.append((int(m.group(4)), m.group(3), int(m.group(2))))

def med(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])

probs = sorted({p for p, _ in d})
rows, better, worse, tie = [], 0, 0, 0
print("%-6s %14s %14s %9s   %s" % ("inst", "sub2", "sub3", "delta", "draws (2 | 3)"))
for p in probs:
    a, b = d.get((p, "sub2")), d.get((p, "sub3"))
    if not a or not b:
        print("P%-5d %14s %14s %9s   incomplete"
              % (p, med(a) if a else "-", med(b) if b else "-", "-"))
        continue
    ma, mb = med(a), med(b)
    dl = 100.0 * (mb - ma) / ma if ma else 0.0
    rows.append((p, dl))
    better += dl < -1e-9; worse += dl > 1e-9; tie += abs(dl) <= 1e-9
    print("P%-5d %14.0f %14.0f %+8.2f%%   %s | %s"
          % (p, ma, mb, dl, ",".join(str(x) for x in a), ",".join(str(x) for x in b)))

if hangs:
    print("\nHANG/CRASH: %s" % ", ".join("P%d %s r%d" % h for h in hangs))
if not rows:
    sys.exit("\nno paired instances yet")

dls = [x for _, x in rows]
print("\npaired instances: %d   sub3 better %d / worse %d / tie %d   median %+.2f%%   mean %+.2f%%"
      % (len(rows), better, worse, tie, med(dls), sum(dls) / len(dls)))

# the eight-instance question, asked directly against the measured per-instance changes
if len(rows) >= 8:
    n8 = tot = 0
    for c in itertools.combinations(dls, 8):
        tot += 1
        if sum(c) / 8.0 < 0:
            n8 += 1
        if tot > 200000:
            break
    print("of %d eight-instance subsets sampled, %.1f%% would have shown sub3 ahead on the mean"
          % (tot, 100.0 * n8 / tot))
