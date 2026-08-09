#!/bin/bash
# prob_1 IS A BERNOULLI DRAW, SO MEASURE THE RATE.
#
# At 240 s prob_1 returns exactly two values and nothing between them:
#
#     470,530   and   501,758     -- 6.2% apart
#
# So "does arm X help prob_1" is not a question about an objective, it is a question about how
# often the run reaches the better attractor.  A single paired cell reads the coin: the same arm
# read -6.64% and +6.22% on consecutive builds of the same idea.  Only a count settles it.
#
# WHAT OGC_WSTAT SHOWED, and it changes the picture.  The four workers are NOT correlated -- they
# are wildly diverse:
#
#     WSTAT round=0 n=4  591921 701832 470530 738497   spread=56.95%
#
# One worker finds the good attractor and the minimum keeps it.  Which means prob_1's outcome is
# decided by whether ANY of four diverse draws lands there, and the direct lever on that is the
# number of draws that survive to be compared.
#
# Which is how the night's most expensive bug was caught.  The same instrument first printed
#
#     WSTAT round=0 n=3  612635 678217 470530 -        spread=44.14%
#
# -- three results and a hole.  maxtasksperchild=1, added hours earlier so each worker gets a clean
# environment, makes a finished worker EXIT; the dead-worker guard tested `exitcode is not None`,
# which was correct only while pool processes lived for the whole round, and counted every normal
# completion as a death.  `want` fell below nw and the collector stopped before the last result
# arrived.  A quarter of the draws, discarded silently, on an instance scored by a minimum over
# them.  Fixed to `exitcode not in (None, 0)`.
#
# This queue measures the rate that fix was supposed to buy, and whether the 7th's direction in half
# the workers raises it further.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo p1rate > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=p1rate" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/p1rate.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p1rate.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: p1rate $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# WSTAT on every cell, so each one also reports whether all four workers delivered and how far
# apart they were.  Arms interleaved so machine drift is shared.
for rep in 1 2 3 4 5 6; do
  run "r$rep.base" 1 240 ""
  run "r$rep.dir"  1 240 "OGC_DIRSET=1"
done
echo "P1RATEDONE" >> $L
echo idle > harness/CURRENT
