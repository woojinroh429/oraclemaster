#!/bin/bash
# GIVE brk THE BUDGET IT HAS NEVER HAD.
#
# brkdiag found the cause and it is starvation, not futility:
#
#     cell                  brk calls   brk s   %budget   brk gain     total
#     stock 60 s                  1       0.4     1.5%           0    712,652
#     beam,brk 60 s               2       2.0     7.6%           0    605,585
#     beam,brk 120 s              2      33.9    44.6%     110,941    533,289
#
# Handed 34 seconds it earns 110,941.  Handed 0.4 it earns nothing -- and earning nothing is what
# keeps it starved, because selection is max(gain/spent) and an operator that returns zero on its
# first short probe is never chosen again.  bayrepack is the one thing in the roster that lifts
# EVERY block out of the contested bay and re-solves the packing with cranepack, which is exactly
# the move class p1_anatomy.md says prob_1 needs -- "_balance moves ONE block ... _z3_improve
# reassigns without re-placing ... every one of them treats the existing arrangement as given, and
# the arrangement is the problem."  It has never been given enough clock to finish that search.
#
# OGC_BRKFLOOR is the smallest slice it will accept, default 8.0 s -- already the largest floor in
# the roster and still under a quarter of what it used productively at 120 s.  This raises it.
#
# WHAT WOULD MAKE IT FAIL, named first.  Every second brk takes comes off the beam, which produced
# every answer this study has recorded, and nobrk_verdict.md already found that removing brk
# entirely is quality-neutral across six instances (median +0.00%, mean +0.18%).  A bigger floor at
# 60 s could simply buy one expensive repack in place of two beam draws.  The 120 s cells are where
# it has room to be worth it; the 60 s cells are where it has to prove it is not merely affordable.
#
# WORKERS=1 so the profile is one worker's and the floor is not diluted across a pool, OPSTAT on so
# the answer is read from brk's own seconds and gain rather than inferred from the total.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo brkbig > harness/CURRENT
L=results/audit/brkbig.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/brkbig.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/brkbig.sh \
        && git commit -q -m "in-flight: brkbig $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" tl="$2" fl="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env OGC_OPSTAT=1 WORKERS=1 OGC_BRKFLOOR=$fl timeout 400 /usr/bin/python3.12 \
        harness/run1.py myalgorithm 1 $tl "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for fl in 8 20 35 50; do
    run "b120.f$fl.r$rep" 120 $fl
  done
done
for rep in 1 2 3; do
  for fl in 8 20 35; do
    run "b60.f$fl.r$rep" 60 $fl
  done
done
echo "BRKBIGDONE" >> $L
echo idle > harness/CURRENT
