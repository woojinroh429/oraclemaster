#!/bin/bash
# The Z1-for-Z3 trade, measured ONLY where the trade is available.
#
# The first attempt put 16 arbitrary instances in one table and was unreadable, because some of
# them cannot make the trade at all.  _late_by returns min(CEIL, w3*regret/w1), so on prob_34 --
# w1 13,333, w3 125, largest preference regret 98 against the 107 needed -- it is identically
# zero and the two arms run the SAME CODE.  That pair still moved 7.67%, which is a direct
# reading of this instance's run-to-run noise, and it was written up as the headline win.
#
# So select on the mechanism.  These twelve have the largest w3 * (total preference regret) / w1
# -- the days of tardiness the whole instance's preference is worth -- and all have both a
# non-zero d_max and slack to spend.  prob_36 is deliberately included: it was the one loss last
# time, and it is fourth in this ranking, so leaving it out would be picking the answer.
#
# Judged by SIGN COUNT over the twelve, not per instance: 10 of 12 one way is p=0.019, and no
# single pair means anything against a 3% spread.
cd "$(dirname "$0")/.."
L=results/audit/latewin2.log; : > $L
for p in 40 26 3 4 13 36 18 27 24 15 17 9; do
  for a in 0 1; do
    OGC_LATEWIN=$a /usr/bin/python3.12 harness/run1.py myalgorithm $p 180 "lw$a" \
        --data data/stage2 >> $L 2>&1
  done
done
echo LATEWIN2DONE >> $L
