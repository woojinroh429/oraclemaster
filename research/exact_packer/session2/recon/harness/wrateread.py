#!/usr/bin/env python3
"""Read wrate.log as replicates: per (budget, instance, arm) print mean, spread and the cells.

The queue exists to answer three questions in order -- does the spread narrow, does the mean hold,
does anything overrun -- so the table prints all three and nothing else.
"""
import re
import sys
from collections import OrderedDict

path = sys.argv[1] if len(sys.argv) > 1 else "build_wrate/results/audit/wrate.log"
pat = re.compile(r"^P(\d+)\s+\[b(\d+)\.p\d+\.(off|on)\.r(\d+)\]\s+\d+s\s+obj=(\d+).*?ran (\d+)s")

cells = OrderedDict()
for line in open(path):
    m = pat.match(line.strip())
    if not m:
        continue
    inst, bud, arm, rep, obj, ran = m.groups()
    cells.setdefault((int(bud), int(inst)), {}).setdefault(arm, []).append((int(obj), int(ran)))

print("%-5s %-5s %-4s %6s %12s %8s %8s  %s" %
      ("bud", "inst", "arm", "n", "mean", "spread", "maxran", "cells"))
for (bud, inst), arms in cells.items():
    for arm in ("off", "on"):
        v = arms.get(arm)
        if not v:
            continue
        objs = [o for o, _ in v]
        rans = [r for _, r in v]
        mean = sum(objs) / len(objs)
        spread = 100.0 * (max(objs) - min(objs)) / min(objs) if min(objs) else 0.0
        print("%-5d P%-4d %-4s %6d %12.0f %7.2f%% %7ds  %s" %
              (bud, inst, arm, len(objs), mean, spread, max(rans),
               " ".join("%d" % o for o in objs)))
    a, b = arms.get("off"), arms.get("on")
    if a and b:
        ma = sum(o for o, _ in a) / len(a)
        mb = sum(o for o, _ in b) / len(b)
        sa = 100.0 * (max(o for o, _ in a) - min(o for o, _ in a)) / min(o for o, _ in a)
        sb = 100.0 * (max(o for o, _ in b) - min(o for o, _ in b)) / min(o for o, _ in b)
        print("      -> mean %+.2f%%   spread %.2f%% -> %.2f%%" %
              (100.0 * (mb - ma) / ma, sa, sb))
