#!/bin/bash
# THE ONE LEVER THAT ADDS DRAWS WITHOUT PAYING FOR THEM, ON THE TWO INSTANCES THAT MATTER.
#
# Deadline is Friday 14:00 and the ask is P1 and P3.  A run's answer is a MINIMUM over the four
# workers' draws, so lowering P1 means producing a better draw -- not a better average.
#
# myalgorithm.py line 109, shipped off since it was written:
#
#   # OGC_SHARE=1 lets a worker that is far behind the others restart from a fresh seed instead of
#   # spending the rest of the budget on a basin the final minimum will discard.  OGC_SHAREGAP is
#   # how far behind it has to be, as a fraction; 0.5 means fifty per cent worse than the best
#   # other worker.  Off by default until measured on the full set.
#
# "Off by default until measured" -- and it never was.
#
# WHY IT IS DIFFERENT FROM EVERYTHING ELSE TRIED THIS SESSION.  Every arm so far either traded
# draw COUNT against draw QUALITY (worker count), or shifted the quality distribution (axis, width,
# w3mul, order, prefw, prefpow) and got absorbed.  SHARE does neither: a worker already far behind
# cannot become the minimum, so the rest of its budget is dead time, and restarting converts that
# into a fresh draw.  More effective draws, no extra contention.
#
# WHAT WOULD MAKE IT FAIL, named first.  Restarting discards a partial solution that might still
# have been improving, and the gap is measured against the best OTHER worker at that moment -- early
# in a run every worker is bad, so a badly placed threshold restarts workers that were merely young.
# That is why the gap is swept: 0.3 restarts eagerly, 0.5 is the written default, 1.0 only abandons
# workers twice as bad.
#
# BOTH BUDGETS, because the hidden limits are unknown and gate120 showed several knobs reversing
# between 60 s and 120 s.  Anything shipped from here has to survive both.
#
# SHIPPED RIG INCLUDING DIRGATE, because that is the build this would go into -- the question is
# whether SHARE adds to what is already there, not whether it works in isolation.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo share13 > harness/CURRENT
L=results/audit/share13.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/share13.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/share13.sh \
        && git commit -q -m "in-flight: share13 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob budget env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 3 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# GAP 0.5 IS DROPPED AFTER ONE CELL, AND THE CELL IS THE REASON.  P1 at 60 s returned
# 556,718 / Z1 20 / Z2 6326 / Z3 674 with the gap at 0.5 and byte-identically without it, so the
# restart never triggered.  The trigger needs a worker 50% worse than the leader between 30% and
# 60% of its budget -- and DIRGATE, which fires here, gives all four workers the same order and
# the same w3mul, so they are far more alike than the stock portfolio and never open that gap.
# 0.3 did fire (548,691, -1.4%), so the live range is below 0.5 and the sweep goes down, not up.
#
# 120 s is dropped too, for the deadline: the hidden set reportedly gives P1 a short limit, that is
# where DIRGATE fires at all, and cells that cost twice as much for a budget we may not face are
# not affordable now.
for rep in 1 2 3; do
  for p in 1 3; do
    run "sh.p$p.60.off.r$rep"  $p 60 "WORKERS=4"
    run "sh.p$p.60.g03.r$rep"  $p 60 "WORKERS=4 OGC_SHARE=1 OGC_SHAREGAP=0.3"
    run "sh.p$p.60.g015.r$rep" $p 60 "WORKERS=4 OGC_SHARE=1 OGC_SHAREGAP=0.15"
    run "sh.p$p.60.g005.r$rep" $p 60 "WORKERS=4 OGC_SHARE=1 OGC_SHAREGAP=0.05"
  done
done
echo "SHARE13DONE" >> $L
echo idle > harness/CURRENT
