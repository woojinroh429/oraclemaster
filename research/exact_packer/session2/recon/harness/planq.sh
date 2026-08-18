#!/bin/bash
# SPLIT THE CPANCH RESULT INTO "THE PLAN WAS BAD" AND "THE BEAM LEFT THE PLAN".
#
# The grid's five draws so far do not separate those two, and they have opposite fixes:
#
#     ca.off.r1          515,188   Z1  25   Z3  543
#     ca.c1.00.t300.r1 1,614,813   Z1 192   Z3  524
#     ca.c0.85.t100.r1   899,486   Z1  32   Z3 1118
#     ca.c0.85.t300.r1 1,580,588   Z1 137   Z3 1085
#     ca.c0.70.t100.r1   703,795   Z1  58   Z3  493
#
# Z3 is not monotone in the de-rating -- 0.85 gives 1118 and 0.70 gives 493 at the same toll --
# so the de-rating cannot be read off the realised Z3 at all.  Either the 0.85 PLAN is bad, or the
# 0.85 plan is fine and the beam walked away from it.  If the plan is bad the fix is to stop
# shrinking area uniformly; if the beam is walking, the fix is the toll on that cell.
#
# This measures the plan alone: one CP-SAT solve per capacity factor, no beam, no timing claim.
# It reports the plan's own Z1 and Z3 and how far the plan sits from the first-choice assignment,
# which is the quantity the de-rating is supposed to move.
#
# NO BEAM RUNS HERE ON PURPOSE.  A solve alongside four beam workers corrupts the timings the grid
# is measuring, so this waits for harness/CURRENT to go idle first and only then takes the cores.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 30; done
echo planq > harness/CURRENT
L=results/audit/planq.log
mkdir -p results/audit
/usr/bin/python3.12 - >> $L 2>&1 <<'PY'
import json, os, sys, time
sys.path.insert(0, '.')
import myalgorithm as M
d = json.load(open('data/stage2/prob_1.json'))
B = d['blocks']; pr = [b['bay_preferences'] for b in B]; n = len(B)
mx = [max(p) for p in pr]; due = [b['due_date'] for b in B]; pt = [b['processing_time'] for b in B]
top = [p.index(max(p)) for p in pr]
print("PLAN QUALITY BY CAPACITY DE-RATING -- CP-SAT only, no beam")
print("  cap    tl     Z1(plan)  Z3(plan)  moved-off-top   w1Z1+w3Z3")
for cf in ("1.00", "0.90", "0.85", "0.80", "0.70", "0.60"):
    os.environ['OGC_CPCAP'] = cf
    for tl in (20,):
        t = time.time(); r = M._cpsat_bay_plan(d, tl); el = time.time() - t
        if r is None:
            print("  %-5s  %-4d  INFEASIBLE / none  (%.1fs)" % (cf, tl, el)); continue
        a, s = r
        z3 = sum(mx[i] - pr[i][a[i]] for i in range(n))
        z1 = sum(max(0, s[i] + pt[i] - due[i]) for i in range(n))
        mv = sum(1 for i in range(n) if a[i] != top[i])
        print("  %-5s  %-4d  %-8d  %-8d  %-13d  %d" % (cf, tl, z1, z3, mv, 6667*z1 + 600*z3))
PY
echo "PLANQDONE" >> $L
echo idle > harness/CURRENT
