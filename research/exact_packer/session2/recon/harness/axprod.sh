#!/bin/bash
# DOES THE 22% AXIS CONCENTRATION SURVIVE INTO THE PRODUCTION PATH?
#
# axis_work.md priced it offline, in work space, on one beam draw:
#
#     prob_16   rotate6 (6 axes x 3000 work)   3,159,373
#               conc1   (axis 2 x 6000 work)   2,477,998    -21.6% for ONE THIRD of the work
#
#     axis 2's margin over the runner-up on prob_16:  2.05x  2.13x  2.51x  2.22x  -- never flips
#
# and then said plainly what it had not shown: "Every number here is ONE BEAM DRAW in work space.
# The shipped algorithm is four workers, an operator loop, and a polish, under a wall-clock budget.
# None of this has been shown to survive that path."
#
# Nobody ran it.  Everything measured in this session -- worker count, rounds, config slots, the
# direction -- moves a draw by single digits, or at best doubles one worker's quality while the
# run's answer barely moves.  This is 22% on an instance whose objective scale matches the hidden
# instance that actually matters, and it is a one-line environment change.
#
# OGC_AXIS=k pins every worker to axis k instead of rotating, so production spends the whole budget
# on axis 2 with the axis's own Bmul and K -- the conc1 shape at wall-clock scale.
#
# THE HONEST RISK, from the same file.  The offline table is at fixed B=96, K=4, while _worker
# sizes each draw from the axis's own Bmul and K -- axis 2 runs at B=67, K=5 in production.  So
# "axis 2 wins" may be a statement about width rather than scoring, and pinning the axis in
# production changes both at once.  If it does not reproduce, that is the first thing to separate.
#
# AND CONCENTRATION REMOVES THE PORTFOLIO.  Rotation exists so a bad axis costs one worker instead
# of the run.  On prob_16 the margin is large and stable, which is the one condition the record
# says makes concentration safe.  On prob_4 the winner FLIPS from axis 2 to axis 1 at the largest
# budget, so prob_4 is the control that shows what pinning costs where the margin is small.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo axprod > harness/CURRENT
L=results/audit/axprod.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/axprod.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/axprod.sh \
        && git commit -q -m "in-flight: axprod $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_WSTAT=1 timeout 560 /usr/bin/python3.12 harness/run1.py myalgorithm $2 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_16 first: the instance with the large, never-flipping axis-2 margin
for rep in 1 2 3; do
  run "p16.stock.r$rep" 16 "WORKERS=4"
  run "p16.ax2.r$rep"   16 "WORKERS=4 OGC_AXIS=2"
done
echo "== AXPROD prob_16 done ==" >> $L
# prob_4: small margin, winner flips at the largest budget -- what pinning costs
for rep in 1 2 3; do
  run "p4.stock.r$rep" 4 "WORKERS=4"
  run "p4.ax2.r$rep"   4 "WORKERS=4 OGC_AXIS=2"
done
echo "AXPRODDONE" >> $L
echo idle > harness/CURRENT
