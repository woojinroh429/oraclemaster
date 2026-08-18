#!/bin/bash
# prob_16 IS THE HIDDEN P1's FAMILY, AND ITS PRODUCTION RESULT IS A 41% LOTTERY.
#
#     249 production runs on prob_16
#       min 2,454,368   p10 2,795,643   median 3,472,568   p90 3,829,684   max 4,807,406
#
# The median is 41% worse than the minimum and only 8 of 249 runs came in under 2.6M.  The user
# reports a friend scoring about 2.4M on the hidden P1 against our 3,051,204.  That is not a
# capability gap: this algorithm already reaches 2.45M, it just reaches it 3% of the time.
#
# THE COMPARISON I GOT WRONG EARLIER TONIGHT, WHICH IS WHY THIS WAS NOT RUN HOURS AGO.
# The deterministic table returns 2,477,998 for ONE beam draw on axis 2 at work 6,000 -- 32 s on a
# single core.  I compared it against production's BEST EVER, 2,469,078, said "production wins by
# 0.4%", and closed the enquiry.  The baseline should have been production's MEDIAN, 3,472,568,
# against which one 32-second construction is 28.6% better.  That is the size of the gap being
# complained about, and I had the number on screen and read it against the wrong column.
#
# THE QUESTION.  Axis pinning failed on prob_1 -- no pinned axis beat the rotation there -- and has
# never been tried on prob_16, where the deterministic advantage of axis 2 over axis 0 is 2.6x, the
# largest single effect measured tonight.
#
# ONE REPLICATE EACH, DELIBERATELY.  prob_16's production spread is wide (p10 2.80M, p90 3.83M),
# but the claimed effect is 28% and the control median is 3.47M.  If axis 2 lands near 2.5M in a
# single cell the effect is larger than the spread and one cell shows it; if it lands at 3.4M the
# claim is dead and more replicates would only be a slower way to learn that.  Axis 2 and the
# rotation run FIRST so the answer arrives in eight minutes rather than half an hour.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo p16axis > harness/CURRENT
L=results/audit/p16axis.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p16axis.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: p16axis $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

run "ax2" 16 240 "OGC_AXIS=2"
run "rot" 16 240 ""
run "ax3" 16 240 "OGC_AXIS=3"
for a in 0 1 4 5; do
  run "ax$a" 16 240 "OGC_AXIS=$a"
done
echo "== P16AXIS single done ==" >> $L

# If axis 2 wins, these price it against the instance's own spread rather than against history.
for rep in 2 3; do
  run "r$rep.ax2" 16 240 "OGC_AXIS=2"
  run "r$rep.rot" 16 240 ""
done
echo "P16AXISDONE" >> $L
echo idle > harness/CURRENT
