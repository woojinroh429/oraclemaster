#!/bin/bash
# THE LIVE QUESTION IS DRAW DEPTH, AND ONLY ONE LEVER STILL POINTS THAT WAY.
#
# The rounds sweep answered its question on the first cell and the answer was no:
#
#     R=1   4 draws of ~228 s   469,427  692,931  428,809  755,086   min 428,809
#     R=2   8 draws of ~120 s   641,965  754,716  630,528  836,872
#                               590,661  639,144  519,486  705,686   min 519,486
#
# Eight tickets and not one under 450,000, against four tickets that caught 428,809.  Doubling the
# count while halving the length is a losing trade, which is what shortdraws.md predicted from the
# 73 s fill round paying 4% over 53 samples.  R=3 and R=4 give ~80 s and ~60 s draws -- shorter
# than the fill round already measured as too short -- so they would confirm a settled answer at
# the cost of half an hour.  Cut.
#
# WHERE THIS LEAVES prob_1.  Saturation is now bracketed: 155 s and 228 s are the same distribution
# over 248 samples, 120 s is clearly worse, 73 s is nearly worthless.  Rounds cannot buy depth
# because R=1 is already the longest round available.  The ONLY remaining way to make a draw deeper
# is to give each worker more of a core, which is the shipped WORKERS=3 -- and it rests on fifteen
# draws:
#
#     WORKERS=4   772 draws   p25 492,458   median 612,635   P(draw<=450k) 0.137  ->  0.45 over 4
#     WORKERS=3    15 draws   p25 469,427   median 489,878   P(draw<=450k) 0.200  ->  0.49 over 3
#
# Three successes out of fifteen puts that 0.200 anywhere from about 0.04 to 0.48, which spans both
# "clearly better than four workers" and "worse".  The shipped default is riding on it.
#
# THIS QUEUE BUYS DRAWS, NOT VERDICTS.  Twenty runs at WORKERS=3 yield sixty draws, four times what
# exists, and each run also produces a run objective for the record.  The comparison target is the
# 772-draw WORKERS=4 pool already on disk, so no control runs are needed.
#
# WHAT WOULD OVERTURN THE SHIPPED DEFAULT.  If the sixty-draw median lands near the WORKERS=4
# median of 612,635 rather than near 489,878, the depth gain was a fifteen-draw accident, three
# workers is one thrown-away ticket for nothing, and the gate comes out.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo p1w3 > harness/CURRENT
L=results/audit/p1w3.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p1w3.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/p1w3.sh \
        && git commit -q -m "in-flight: p1w3 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 560 /usr/bin/python3.12 harness/run1.py myalgorithm 1 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in $(seq 1 20); do
  run "w3.r$rep" "WORKERS=3"
done
echo "P1W3DONE" >> $L
echo idle > harness/CURRENT
