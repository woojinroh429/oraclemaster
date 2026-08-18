#!/bin/bash
# DOES A CHEAP BEAM-ONLY RUN PREDICT WHICH AXIS WINS THE FULL RUN?
#
# The proposal it gates: the opening axis largely decides the answer -- the loop's own trace on
# the hidden P6 at 300 s recorded the first beam producing the best solution of the entire run in
# 33 seconds, and the other 267 never beating it -- and there are far more candidate openings
# (6 axes x 7 orders x a parameter grid) than the four opening slots nw=4 allows.  So a short
# prologue could audition candidates and hand the slots to whichever wins ON THIS INSTANCE,
# instead of using a fixed set chosen on the preliminary data before 08-02.
#
# ortho is why this is worth asking rather than assumed dead.  Replacing the axis set reached
# answers base never reaches -- prob_4 -5.69%, prob_6 -4.19%, the latter 1.7% below the best of
# five base draws -- and it lost only because it DISCARDED base's axes and with them their
# attractors (prob_13 +17.0%, prob_20 +17.7%).  Choosing per instance keeps both.
#
# WHAT WOULD KILL IT, and has to be measured first: if beam-time rank does not survive the
# operator loop, the prologue selects on a signal that is gone by the end.  The aim race already
# got this exact thing wrong -- on prob_34 the arm leading at 25% of budget lost at full depth,
# and committing to it cost 5.45%.
#
# So: for each axis, a 60 s beam-ONLY run (OGC_OPS=beam, the roster reduced to the beam operator)
# against a 240 s full run (whole roster), both with OGC_AXIS pinning every worker to that axis.
# The question is the rank correlation between the two columns, per instance.  60 s is not an
# arbitrary probe length -- it is roughly what a prologue could afford out of 240.
#
# This also answers "should the beam be made better".  If beam rank predicts final rank, beam
# quality reaches the answer and improving it pays.  If it does not, the operator loop washes it
# out and beam work cannot survive to the score.
set -u
cd "$(dirname "$0")/.." || exit 1
echo audition > harness/CURRENT
L=results/audit/audition.log
mkdir -p results/audit; touch $L

run(){ # arm prob axis secs env
    local tag="$1.a$3.$2"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env OGC_AXIS=$3 $5 timeout 960 /usr/bin/python3.12 harness/run1.py myalgorithm $2 $4 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$2 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/audition.log \
      && git commit -q -m "in-flight: audition $tag" ) >/dev/null 2>&1
}

# six instances spanning the exchange-rate range, the same ones ortho and nobrk used so the logs
# cross-reference
for p in 4 26 20 2 6 13; do
    for k in 0 1 2 3 4 5; do
        run beam $p $k 60  "OGC_OPS=beam"
        run full $p $k 240 ""
    done
    echo "INSTDONE $p" >> $L
done
echo "AUDITIONDONE" >> $L
echo idle > harness/CURRENT
