#!/bin/bash
# SEPARATE "MORE TIME" FROM "DIRGATE OFF", WHICH flatcurve CANNOT DO.
#
# MY OWN ERROR, corrected here rather than worked around.  flatcurve.sh states that the 60->180
# step is clean on DIRGATE.  It is not.  The gate's condition is `timelimit <= OGC_DIRGATET`
# (myalgorithm.py:4673, default 60), so DIRGATE fires at 20 s and 60 s and does NOT fire at 180 s.
# Every configuration boundary in that script lands on a step it was meant to measure:
#
#     20 s    DIRGATE on    MGATE off (its floor is 60)
#     60 s    DIRGATE on    MGATE on
#    180 s    DIRGATE OFF   MGATE on
#
# prob_1's first curve reads 712,040 / 663,005 / 489,878.  The 60->180 drop is -26.1% and it is
# NOT attributable: it is more time AND the direction gate switching off, confounded in one step.
#
# THIS SPLITS THEM.  Both knobs already exist -- OGC_DIRGATE=0 forces the gate off, and
# OGC_DIRGATET=300 raises its budget ceiling so it fires at 180 s too.  Four cells per instance:
#
#     60 s  gate ON    the shipped configuration
#     60 s  gate OFF
#    180 s  gate ON    (DIRGATET=300)
#    180 s  gate OFF   what flatcurve's 180 s cell actually was
#
# Reading down a column gives the TIME effect at a fixed configuration; reading across a row gives
# the GATE effect at a fixed budget.  flatcurve's number was the diagonal.
#
# WHY IT MATTERS BEYOND THE BOOKKEEPING.  If the -26.1% is mostly time, prob_1 is simply not
# converging in 60 s and the lever is draws and allocation.  If it is mostly the gate, then DIRGATE
# -- which we ship, and which fires on exactly the loose Z3-dominated instances we lose to the
# competitor -- is COSTING us on prob_1 at 60 s, and the fix is a gate condition rather than more
# search.  Those two conclusions point at opposite work, which is why the diagonal is not good
# enough to act on.
#
# WHAT WOULD MAKE IT FAIL, named first.  prob_1 spans roughly 30% between draws on unchanged code
# in this build, so a 5-10% cell-to-cell difference is not a finding here; only the -26% class of
# gap is large enough to attribute at two replicates, and anything smaller gets reported as
# undecided rather than dressed up.  prob_3 is carried because it is the other instance we lose
# and it is far less noisy, so it is the better test of the gate effect even though prob_1 is the
# instance the question came from.
#
# JUDGED, fixed before the run: within-instance ratios only, never across instances.  The verdict
# is which of the two effects is larger on prob_3, with prob_1 as support.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire flatctl
L=results/audit/flatctl.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/flatctl.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/flatctl.sh \
        && git commit -q -m "in-flight: flatctl $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" tl="$3" env0="$4" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p $tl "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2; do
  for p in 3 1; do
    run "g60on.p$p.r$rep"   $p  60 "OGC_DIRGATE=1"
    run "g60off.p$p.r$rep"  $p  60 "OGC_DIRGATE=0"
    run "g180on.p$p.r$rep"  $p 180 "OGC_DIRGATET=300"
    run "g180off.p$p.r$rep" $p 180 "OGC_DIRGATE=0"
  done
done
echo "FLATCTLDONE" >> $L
lock_release flatctl
