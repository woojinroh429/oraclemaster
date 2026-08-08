#!/bin/bash
# THE BEAM'S ONLY LOOKAHEAD SCORES ENTRY AGAINST A DUE DATE THAT APPLIES TO EXIT.
#
# Z1 is sum over blocks of max(0, EXIT - due), and exit is entry + processing_time.  wb_hz1 -- the
# free-capacity relaxation the beam adds to its rank as w1*hz1, and its only view past the block it
# is placing -- computes tau, the time by which an unplaced block's area can be absorbed, and
# compares tau directly against due.  tau is an ENTRY.  So every unplaced block is scored as though
# it left the yard the instant it arrived, and the whole of sum(pt) is missing from the lookahead --
# missing unevenly, since a long-processing block against a tight due date reads as free.
#
# The same loop uses the earliest release in the set to start its clock and then treats every block
# as available from that moment, so a late-released block is credited with time it does not have.
#
# Both errors point the same way: the estimate is too LOW, and a lookahead that understates future
# tardiness is precisely what lets a beam prefer states that look cheap now and finish late.  It is
# a RANK term -- wb_lb is the pruning bound and is untouched -- so raising it cannot prune the
# optimum, only change which states survive.
#
# First reading, 30 s, back to back on the same machine:
#
#     P6   off 5,844,343  Z1=369      on 5,364,185  Z1=341     -8.22%
#     P1   off   639,495              on   639,495              0.00%   (identical)
#
# prob_6 carries 85% of its objective in w1*Z1 and prob_1 22.6%, so the split is what the change
# predicts: where tardiness is what the objective is made of, a lookahead that can finally see
# processing time moves the search; where it is not, nothing happens.
#
# WHAT THIS QUEUE HAS TO SHOW.  Per-instance scoring, so: does it hold at the long budget, does it
# hold on the Z1-heavy instances it should help, and does it cost nothing on the ones it should not
# touch.  Two replicates because the arm difference has to clear the instance's own spread.
#
# BOTH ARMS ON THE SAME FRESH BINARY in build_hz1 -- unset env is a no-op in the source and not in
# the binary.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon/build_hz1 || exit 1
echo hz1 > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=hz1" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/hz1.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/build_hz1/results/audit/hz1.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: hz1 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# The Z1-heavy instances first, because they are where the argument says the effect is, and a
# campaign that runs out of night should have spent it on the decisive cells.  Arms interleaved
# within an instance so machine drift cannot be read as an arm difference.
for rep in 1 2; do
  for p in 6 36 16 20 1; do
    run "b240.p$p.off.r$rep" $p 240 ""
    run "b240.p$p.on.r$rep"  $p 240 "OGC_HZ1V2=1"
  done
  echo "== HZ1 240 rep $rep done ==" >> $L
done
echo "HZ1DONE" >> $L
echo idle > harness/CURRENT
