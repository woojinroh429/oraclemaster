#!/bin/bash
# DOES ANY OF THE NIGHT'S WORK-SPACE FINDING SURVIVE THE REAL PIPELINE?
#
# Three knobs came out of the work-budgeted sweeps, all noise-free, all pointing the same way on
# instances where w3*Z3 carries the objective:
#
#     dispatch order   prob_1 axis-0 params: defer_big 1,174,681 -> lst 690,840      -41.2%
#     w3mul            prob_1 axis 2: default band 684,687 -> 0.5 587,906            -14.1%
#                      prob_1 axis 3: 1.0 737,578 -> 0.5 612,492                     -17.0%
#     polish reserve   prob_1 full pipeline: 40 s 501,758 -> 120 s 470,530            -6.2%
#
# All of it except the reserve is ONE BEAM DRAW in work space.  The shipped run is four workers, an
# operator loop, and a polish, under a wall clock -- and this session already has a case where a
# work/area-space result of -97% became +10x once the real constraints were applied (the best-bay
# construction).  So nothing ships until it is measured here.
#
# ARMS.  Each isolates one knob, then the combination, so an interaction can be seen rather than
# assumed.  The two beam knobs go in through OGC_AXSET-style overrides is not available, so they are
# applied by env to every axis at once:
#
#     base   as shipped
#     o      OGC_ORDER=lst        every axis dispatches by latest-start-time
#     w      OGC_W3MUL=0.5        every axis scales w3 by 0.5 in the bay ranking
#     r      OGC_RESERVE=120      half the budget to the polish instead of 40 s
#     owr    all three
#
# INSTANCES.  prob_1 and prob_4 are where the work-space wins were, and both have baselines that
# repeat to the last digit, so one cell decides. prob_24, prob_16 and prob_20 are where the same
# knobs LOST in work space -- if they lose here too the rule is conditional on the Z3 share and the
# ship decision has to carry that condition; if they do not lose, the knobs are simply better.
#
# READ THE WORST INSTANCE, not the mean.  Scoring is per instance, so a change that averages -5%
# while costing 20% on one instance is not shippable.
set -u
cd "$(dirname "$0")/.." || exit 1
echo combo > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=combo" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/combo.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/combo.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: combo $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py myalgorithm \
        $2 240 "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_1 first and every arm on it before moving on: it is the target instance, it is noise-free,
# and if nothing moves there the rest of the queue is not worth the machine time.
for rep in 1 2; do
  for p in 1 4 24 16 20; do
    run "r$rep.base.$p" $p ""
    run "r$rep.o.$p"    $p "OGC_ORDER=lst"
    run "r$rep.w.$p"    $p "OGC_W3MUL=0.5"
    run "r$rep.r.$p"    $p "OGC_RESERVE=120"
    run "r$rep.owr.$p"  $p "OGC_ORDER=lst OGC_W3MUL=0.5 OGC_RESERVE=120"
  done
done
echo "COMBODONE" >> $L
echo idle > harness/CURRENT
