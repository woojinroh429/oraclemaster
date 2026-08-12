#!/bin/bash
# HAND THE BEAM THE PLAN'S TIMES, NOT ITS BAYS -- THE ONE CHANNEL NEVER TRIED.
#
# Two friends solving this with MIP score 2.4M and 2.5M on the hidden P1 against our 2,796,931.
# That is 12-14%, and it is not a tuning gap; it says the instance is decided by planning, which is
# what assignment_first.md already concluded from our own CP-SAT relaxation:
#
#     plan       Z1  1   Z3 403     248,467
#     realised   Z1 44   Z3 590     667,853
#
#     "The bays are nearly obeyed -- 145 of 150 blocks sit where the plan put them.  The gap is
#      entirely in time.  The plan reaches Z1 = 1 by making 37 blocks WAIT up to nine units past
#      their release; the beam never sees those times, dispatches in its axis's own order, and has
#      to rediscover the same seating."
#
# Two channels were tried and neither carries a schedule.  OGC_CPANCHW tolls the preferences, which
# says WHERE and is measured monotonically bad (515,188 / 703,795 / 1,849,481 at tolls 0 / 100 /
# 300).  OGC_CPORD hands over planned-start ORDER, which says who goes first and still lets the
# beam seat everyone as early as it can.
#
# OGC_CPRT raises each block's RELEASE TIME to its planned start.  That is the one field in the
# instance that says WAIT, every stage already honours it, and nothing is pinned -- a block may
# still go later if the packing demands it.  The toll is switched off (OGC_CPANCHW=0, a path opened
# for this) so the times are priced alone; with it on, every earlier CPRT reading was the toll plus
# the times.  Smoke: 598,517 against control draws of 683,809 and 605,585.
#
# WHAT WOULD MAKE IT FAIL, named first.  The plan's times are computed under an AREA relaxation
# with no 2D packing, so a block told to wait may find its bay full anyway when it arrives -- and
# it has now given up the earlier slot it could have had.  That is a strictly worse position than
# arriving early and being pushed, which is what the beam does today.  The CP-SAT solve also costs
# 15 s of a 60 s budget before any search starts.
#
# JUDGED: six draws each on prob_1 -- the control spans 605k-684k tonight, so fewer cannot resolve
# the 5-10% this would have to be worth.  prob_3 and prob_16 gate it afterwards.
#
# RUN AT 120 s, NOT 60.  The CP-SAT solve is a fixed cost paid before any search starts -- 15 s of a
# 60 s budget is a quarter of the run handed to the planner, which prices the plan against a search
# that has been robbed to pay for it.  At 120 s with a 25 s solve the overhead halves and the
# question becomes what the plan is worth rather than what it costs.
#
# IT ALSO CHANGES THE CONFIGURATION, DELIBERATELY RECORDED: DIRGATE fires only at timelimit <= 60,
# so these cells run WITHOUT the lst order, the halved w3 and the 0.50 reserve that the shipped
# 60 s path installs.  Whatever this measures transfers to a 120 s grader directly and to a 60 s
# one only as a direction.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo cprt120 > harness/CURRENT
L=results/audit/cprt120.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/cprt120.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/cprt.sh \
        && git commit -q -m "in-flight: cprt $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" envs="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $envs timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm $p 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3 4 5 6; do
  run "c.p1.ctl.r$rep"  1 "OGC_DEBUG=0"
  run "c.p1.rt.r$rep"   1 "OGC_CPANCH=25 OGC_CPANCHW=0 OGC_CPRT=1"
done
for rep in 1 2 3; do
  for p in 3 16; do
    run "c.p$p.ctl.r$rep" $p "OGC_DEBUG=0"
    run "c.p$p.rt.r$rep"  $p "OGC_CPANCH=25 OGC_CPANCHW=0 OGC_CPRT=1"
  done
done
echo "CPRTDONE" >> $L
echo idle > harness/CURRENT
