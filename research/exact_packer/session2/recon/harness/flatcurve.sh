#!/bin/bash
# ARE WE ACTUALLY BAD AT FLAT INSTANCES, OR JUST FINISHED WITH THEM?
#
# THE OBSERVATION.  Against a competitor's scoreboard we win six of eight and lose exactly two:
# hidden P1 by 1.37% and hidden P3 by 6.41%.  Scoring is per-instance rank summed, so those two
# cost real positions.
#
# THE HYPOTHESIS, from the user: our edge is cranepack, the exact packer for multi-layer blocks,
# and on instances whose blocks are all flat that edge never fires -- we are doing the same 2D
# packing as everyone else and have nothing extra.
#
# THE LAYER DATA SUPPORTS THE SETUP AND NOT YET THE CONCLUSION.  Across all forty stage-2
# instances the split is bimodal with nothing between 1.90 and 2.91:
#
#     31 instances   mean 1.80-1.90 layers/block   every block 1-2 layers   0% at >=3
#      9 instances   mean 2.91-3.10                blocks 1-4              62-73% at >=3
#
# prob_1 (1.85) and prob_3 (1.90) are both flat.  But so are 31 of 40, so flatness alone cannot
# explain losing 2 of 8 -- that needs the hidden set to be unusually layered, which we cannot see
# and must not assume.
#
# SO MEASURE THE THING THAT DOES NOT NEED THE ASSUMPTION.  Give each instance 20 s, 60 s and 180 s
# and read the SHAPE of the curve:
#
#   * flat curve (20 ~ 60 ~ 180) -> the search is done; more time buys nothing, and what is missing
#     is a move class rather than a budget.  On prob_1 that would fit what this session already
#     found: fourteen different approaches all landing in the same small set of attractors, and
#     prob_1 already placing 138 of 150 blocks at their release time with 14 units of tardiness.
#   * still falling at 180 -> we are simply not converging in 60 s, and draws / time allocation are
#     the lever after all.
#
# AND THE COMPARISON IS THE POINT.  prob_1 and prob_3 are the flat instances we lose; prob_5 and
# prob_39 are the two most layered in the set (2.99 and 3.10, 64% and 73% at >=3 layers).  If the
# layered pair keeps improving with time while the flat pair goes flat, the cranepack story has
# evidence.  If both pairs behave the same way, the story is wrong and the loss is about something
# else -- which is just as useful, because it closes a direction I would otherwise keep spending on.
#
# WHAT WOULD MAKE IT MISLEAD, named first.  Absolute objectives are not comparable across
# instances, so everything is read as a RATIO to that instance's own 20 s cell, never across
# instances.  And single draws on prob_1 span 30% in this build, so two replicates at each budget
# is the floor for reading a curve at all -- a 10% step between budgets is inside one instance's
# noise and will not be called a trend.
#
# 20 s is also below MGATE's 60 s floor and DIRGATE's <=60 s condition, so the 20 s cells run a
# DIFFERENT configuration from the 60 s ones.  That is a confound for the 20->60 step specifically;
# the 60->180 step is clean on DIRGATE (both fire nothing at 180) and is the one to trust.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire flatcurve
L=results/audit/flatcurve.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/flatcurve.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/flatcurve.sh \
        && git commit -q -m "in-flight: flatcurve $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" tl="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p $tl "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
# flat pair first (the two we lose), then the layered pair.
for rep in 1 2; do
  for p in 1 3 5 39; do
    for tl in 20 60 180; do
      run "t$tl.p$p.r$rep" $p $tl
    done
  done
done
echo "FLATCURVEDONE" >> $L
lock_release flatcurve
