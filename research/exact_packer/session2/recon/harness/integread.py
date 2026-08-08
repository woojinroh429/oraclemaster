#!/usr/bin/env python3
"""Read integ.log grouped by phase and instance, each arm as a percentage against that group's base.

Scoring is per instance, so the table never pools: an arm that wins the median and loses one
instance by 15% has not won anything.  The base-to-base gap between the a60 and d60 groups -- the
same cell run twice by construction -- is printed at the end as this queue's own noise estimate.
"""
import re
import sys
from collections import OrderedDict

path = sys.argv[1] if len(sys.argv) > 1 else "results/audit/integ.log"
pat = re.compile(r"^P(\d+)\s+\[([a-z]+\d+)\.p\d+\.([A-Za-z0-9._]+)\]\s+\d+s\s+obj=(\d+)")

g = OrderedDict()
for line in open(path):
    m = pat.match(line.strip())
    if not m:
        continue
    inst, phase, arm, obj = m.groups()
    g.setdefault(phase, OrderedDict()).setdefault(int(inst), OrderedDict())[arm] = int(obj)

BASE = {"a": "base", "d": "base", "r": "R1"}
for phase, insts in g.items():
    ref = BASE.get(phase[0], "base")
    print("\n== %s ==  (reference arm: %s)" % (phase, ref))
    arms = []
    for a in insts.values():
        for k in a:
            if k not in arms:
                arms.append(k)
    print("%-6s %s" % ("inst", " ".join("%14s" % a for a in arms)))
    for inst, a in insts.items():
        b = a.get(ref)
        cells = []
        for k in arms:
            v = a.get(k)
            if v is None:
                cells.append("%14s" % "-")
            elif b:
                cells.append("%9d%+5.1f%%" % (v, 100.0 * (v - b) / b))
            else:
                cells.append("%14d" % v)
        print("P%-5d %s" % (inst, " ".join(cells)))
    # per-arm tally, never pooled into a single number
    for k in arms:
        if k == ref:
            continue
        d = [(100.0 * (a[k] - a[ref]) / a[ref]) for a in insts.values() if k in a and a.get(ref)]
        if d:
            print("   %-6s wins %d/%d   worst %+.2f%%   best %+.2f%%"
                  % (k, sum(1 for x in d if x < 0), len(d), max(d), min(d)))

a60 = g.get("a60", {})
d60 = g.get("d60", {})
pairs = [(i, a60[i]["base"], d60[i]["base"])
         for i in a60 if "base" in a60.get(i, {}) and "base" in d60.get(i, {})]
if pairs:
    print("\n== base vs base: the same cell run twice, this queue's own noise floor ==")
    for i, x, y in pairs:
        print("P%-5d %9d %9d %+6.2f%%" % (i, x, y, 100.0 * (y - x) / x))
