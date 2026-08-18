"""Pool the per-operator accounting across instances.

Each run prints one opstat block per worker, so a 12-instance sweep is 48 blocks.  What matters is
not any single block -- gain is credited only when that worker's incumbent improves, which is noisy
-- but the pooled share of budget against the pooled share of gain.  An operator holding 20% of the
budget and producing 0% of the gain across 48 blocks is a different claim from one doing it twice.

Prints, per operator: total seconds, share of measured budget, total gain, share of gain, and the
count of blocks where it returned exactly zero.

    usage: python3.12 harness/opread.py [logfile]
"""
import os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/opcost.log")
ROW = re.compile(r"^\s*opstat\s+(\w+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)%\s+(\d+)\s+([\d.]+)")

secs = defaultdict(float); gain = defaultdict(float)
tried = defaultdict(int); zeros = defaultdict(int); blocks = defaultdict(int)
for ln in open(LOG, errors="replace"):
    m = ROW.match(ln)
    if not m or m.group(1) == "TOTAL":
        continue
    op = m.group(1)
    tried[op] += int(m.group(2)); secs[op] += float(m.group(3))
    g = float(m.group(5)); gain[op] += g; blocks[op] += 1
    if g == 0.0:
        zeros[op] += 1

if not secs:
    sys.exit("no opstat rows yet")
TS = sum(secs.values()); TG = sum(gain.values()) or 1.0
print("%-6s %7s %9s %8s %14s %8s   %s" % ("op", "tried", "seconds", "%budget", "gain", "%gain", "zero blocks"))
for op in sorted(secs, key=lambda o: -secs[o]):
    print("%-6s %7d %9.1f %7.1f%% %14.0f %7.1f%%   %d/%d"
          % (op, tried[op], secs[op], 100 * secs[op] / TS, gain[op], 100 * gain[op] / TG,
             zeros[op], blocks[op]))
print("\n%-6s %7d %9.1f %7.1f%% %14.0f %7.1f%%" % ("TOTAL", sum(tried.values()), TS, 100.0, TG, 100.0))
print("\nAn operator well above its gain share is a candidate for ablation, not for deletion:")
print("gain counts only improvements to the incumbent, so a useful-but-never-best operator reads 0.")
