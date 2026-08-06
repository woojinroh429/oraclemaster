#!/bin/bash
# PAIR THE SECOND AND THIRD SUBMISSIONS, ON THE PACKAGES THAT WERE ACTUALLY MAILED.
#
# The three submitted totals are 74,003,416 / 73,283,064 / 73,981,407 -- 1 to 3 is -0.0% -- and
# that reads as "a day and a half of work bought nothing".  It may not mean that.  Both changes
# between the second and the third submission were validated on the 40-instance final training
# set, and the final round scores only EIGHT instances.  Split-aim measured a -3.44% median over
# 37 paired instances; on eight draws, against a per-instance spread that b240 put at 0.66% to
# 16.2% for the same build on the same instance, that effect is not resolvable.  So the flat
# total is equally consistent with "no improvement" and with "a real improvement buried in the
# draw noise", and those two call for opposite decisions about what to do next.
#
# WHAT SEPARATES THE TWO BUILDS.  Diffing the submitted sources rather than trusting the report:
#
#   beam salvage        Python and C++.  The beam used to return NOTHING when it ran past its
#                       deadline, dropping the caller to _safe_sequential -- a cliff, not a
#                       slope.  Smoke test just now on P24 at 30 s: sub2 647,922,415, sub3
#                       2,591,153.  250x, and that is the cliff in one line.
#   split-aim           workers alternate beam aim 0.90 / 0.10; the answer is their minimum.
#   late-window ladder  OGC_LATEK, default 1 -- byte-identical behaviour, not a difference.
#   OGC_ROUNDS          default 1 -- same.
#   ABI source stamp    no behaviour.
#
# So two live changes, and the first of them is a floor-raiser whose size depends entirely on
# whether the budget is enough for the beam to finish.  That is why this runs at 240 s and not at
# the 60 s everything else today used: at 30 s the cliff is everywhere and the result would say
# nothing about a real run.
#
# All forty instances, both arms, paired on the same instance, rep-major so a partial queue is a
# balanced sample rather than the first ten instances.  _total is byte-identical between the two
# builds, so the scorer is not a confound.  Both packages still contain the double-move segfault
# found on 08-06 and neither has the bounded-wait pool, so a crash hangs the run forever -- hence
# the timeout, and a HANG line rather than a silently missing one.
set -u
cd "$(dirname "$0")/.." || exit 1
echo pair23 > harness/CURRENT
L=results/audit/pair23.log
mkdir -p results/audit; touch $L
[ -d builds/sub3 ] || bash harness/subbuild.sh

run(){ # rep arm prob
    local tag="r$1.$2.$3"
    grep -q "\[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    timeout 700 /usr/bin/python3.12 harness/subrun.py "builds/$2" $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/pair23.log \
      && git commit -q -m "in-flight: pair23 $tag" ) >/dev/null 2>&1
}

# front-loaded with the instances whose behaviour is already characterised (P16 the unstable one,
# P6/P20/P1 the spread ladder from b240), then everything else, so an early read is informative.
ORDER="16 6 20 1 24 36 25 13 3 12 26 30 2 4 5 7 8 9 10 11 14 15 17 18 19 21 22 23 27 28 29 31 32 33 34 35 37 38 39 40"
for rep in 1 2; do
    for p in $ORDER; do
        run $rep sub2 $p
        run $rep sub3 $p
    done
    echo "REPDONE $rep" >> $L
done
echo "PAIR23DONE" >> $L
echo idle > harness/CURRENT
