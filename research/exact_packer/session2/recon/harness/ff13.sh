#!/bin/bash
# P1 IS BUDGET-LIMITED, NOT DIRECTION-LIMITED, AND THIS IS THE KNOB THAT BUYS REACH.
#
# The same code on stage2/prob_1: 556,718 at 60 s, 492,989 at 120 s, 422,629 at 240 s.  The search
# is not stuck in a bad basin at 60 s -- it has not finished.  That also explains DIRGATE, which
# wins at 60 s and loses at 120 s: it arrives sooner, not better.
#
# So more P1 at a short budget means reaching further per second.  Two construction paths were
# closed today trying to get there another way: CP-SAT plan + _realise tops out at 880,373 against
# the beam's 556,718 (greedy single-pass placement wastes too much space), and forcing the beam to
# obey the plan costs Z1 = 254.  The plan's Z3 = 403 is simply not reachable at low Z1 by anything
# we have -- the area relaxation ignores that 2D packing wastes space.
#
# OGC_FINEFRAC splits the construction budget between the two rungs:
#
#     for step, frac in ((1, _ff), (2, 1.0)):     _ff default 0.6
#
# step 1 is the fine grid, step 2 the coarse one.  At 60 s the fine rung gets 60% of a small slice,
# and the file's own note says it is being cut off mid-improvement: "prob_1's best axis is still
# improving at work 12,000 (51 s) while production stops it around 9 s, so a longer fine rung is
# exactly what that curve asks for."  Written, never tested -- task #13 has been pending all day.
#
# WHAT WOULD MAKE IT FAIL, named first.  frac comes out of what is LEFT, so a longer fine rung
# starves step 2 -- and step 2 exists because instrumented runs on prob_18 showed two of three beam
# calls returning NOTHING when the fine rung got the whole slice.  Both directions are swept for
# that reason: 0.85 lengthens the fine rung, 0.35 shortens it.  A collapse on either instance is
# decisive against.
#
# JUDGED ON BOTH INSTANCES, fixed before the run: below control on P1 AND P3 in at least two of
# three replicates.  Seven settings have failed to transfer between instances today.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo ff13 > harness/CURRENT
L=results/audit/ff13.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ff13.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/ff13.sh \
        && git commit -q -m "in-flight: ff13 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3; do
    run "f.p$p.60.r$rep"  $p "WORKERS=4"
    run "f.p$p.85.r$rep"  $p "WORKERS=4 OGC_FINEFRAC=0.85"
    run "f.p$p.95.r$rep"  $p "WORKERS=4 OGC_FINEFRAC=0.95"
    run "f.p$p.35.r$rep"  $p "WORKERS=4 OGC_FINEFRAC=0.35"
  done
done
echo "FF13DONE" >> $L
echo idle > harness/CURRENT
