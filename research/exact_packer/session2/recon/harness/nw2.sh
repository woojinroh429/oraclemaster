#!/bin/bash
# FEWER, BETTER DRAWS.  THE DIRECTION THE OVERSUBSCRIPTION SLOPE POINTS AT.
#
# nw.sh measured the other side and it was the largest effect of the night:
#
#     prob_1, 120 s, r1     w4  584,609     w6  701,633  +20.0%     w8  671,556  +14.9%
#
# Cutting each worker's share of a core from 1.00 to 0.67 cost 20%.  That slope is steep enough
# that the reverse is worth pricing: three workers get 1.33 cores each, two get 2.00.
#
# THE TRADE, WITH ONE SIDE ALREADY MEASURED.  The score is a minimum over the workers, so halving
# the worker count halves the number of draws the minimum is taken over, and prob_1's draws are
# spread over a heavy left tail -- 456 distinct values in 1,176 results.  Losing draws costs.  What
# nw.sh established is the size of the OTHER term: 0.67 cores per worker is worth -20%, so 2.00
# cores per worker is a large quantity too, and the question is only which is larger.
#
# WHY THIS IS ALSO A VARIANCE EXPERIMENT, WHICH IS THE STATED GOAL.  Two workers means the answer
# is a min over two, which is MORE variable run to run, not less.  So if w2 wins on the mean and
# loses on the span, it is the wrong trade for a per-instance score where the worst run sets the
# tier.  The report is mean, worst cell and span per arm -- not the mean alone.
#
# AND THE GRADER HAS FOUR CORES.  Confirmed by the user.  So w4 is the setting that gives every
# worker exactly one core, and both directions away from it are being priced against that.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nw2 > harness/CURRENT
L=results/audit/nw2.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nw2.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: nw2 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4 5; do
  run "r$rep.p1.w4" 1 120 "WORKERS=4"
  run "r$rep.p1.w3" 1 120 "WORKERS=3"
  run "r$rep.p1.w2" 1 120 "WORKERS=2"
done
echo "== NW2 prob_1 done ==" >> $L

for rep in 1 2 3 4; do
  run "r$rep.p16.w4" 16 120 "WORKERS=4"
  run "r$rep.p16.w3" 16 120 "WORKERS=3"
  run "r$rep.p16.w2" 16 120 "WORKERS=2"
done
echo "NW2DONE" >> $L
echo idle > harness/CURRENT
