#!/bin/bash
# IS IT THE ROUND'S ABSOLUTE LENGTH?  One instance, one question, six cells.
#
# prob_16 against round length, every number below read from a log:
#
#     236 s per round   (240 s, R=1)   3,661,692
#     118 s per round   (240 s, R=2)   3,704,126
#      78 s per round   (240 s, R=3)   3,756,392
#      47 s per round   ( 60 s, R=1)   3,513,968      <- and this repeated 4/4 to the digit
#      23 s per round   ( 60 s, R=2)   2,796,522      <- 4/4 to the digit, -23.6% on the best above
#
# Inside the 240 s budget, shortening the round makes it monotonically WORSE.  Yet the two 60 s
# points are better than all three, and the 23 s point is better by 23% than anything this project
# has produced on prob_16 at 240 s in a dozen runs today.  Every 240 s point sampled so far sits
# above 78 s, so the cliff between 47 s and 23 s has never been crossed at the real budget.
#
# R=10 puts a 240 s run at 23.6 s per round -- the same round length as the 60 s R=2 cell, with
# four times as many of them.  That is the whole experiment.
#
#     effect is the ROUND LENGTH        -> R=10 lands near 2.8M and there is a 23% lever here
#     effect is the BUDGET itself       -> R keeps degrading and the knob is finished
#
# THE POSITIVE CONTROL IS NOT OPTIONAL.  The 2,796,522 cells were recorded by an older build.  If
# the 60 s R=2 cell does not still return that number, the premise of this queue is gone and every
# conclusion drawn from those old cells has to be re-opened rather than extended.  It runs first.
#
# One instance is deliberate, and it is not the conclusion -- it is the screen.  A 23% effect
# either shows here or it does not exist; prob_16's own run-to-run spread today is 5.2%, so
# anything near 20% is unmistakable at n=1.  If it shows, the queue that follows is the one that
# matters: the same sweep across the other instances, because an effect that only appears on
# prob_16 is a property of prob_16.
set -u
cd "$(dirname "$0")/.." || exit 1
echo roundlen > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=roundlen" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/roundlen.log
mkdir -p results/audit; touch $L

run(){ # tag prob secs R
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_ROUNDS=$4 OGC_WSTAT=1 timeout $(( $3 * 5 )) \
        /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$2 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/roundlen.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: roundlen $tag" ) >/dev/null 2>&1
}

# control first: does the old 2,796,522 still come out of today's build?
run "ctl60R2.16"  16  60  2
run "ctl60R1.16"  16  60  1
# then the sweep at the real budget, shortest round first -- that is where the claim lives
run "s240R10.16"  16 240 10
run "s240R16.16"  16 240 16
run "s240R6.16"   16 240  6
run "s240R4.16"   16 240  4
echo "ROUNDLENDONE" >> $L
echo idle > harness/CURRENT
