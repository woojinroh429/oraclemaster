#!/bin/bash
# WAS THE POLISH TURNED OFF ON A MEDIAN THAT HID ITS TAIL?
#
# What forced this queue.  prob_16 at 60 s with OGC_ROUNDS=2 returned 2,796,522 in four separate
# replicates, to the last digit, on an older build.  Today's build returns 3,835,016 for the same
# cell -- so that number was never a property of the rounds knob.  The largest behavioural
# difference between the two builds is that the final polish now defaults OFF.
#
# The polish was retired on this measurement: across 804 runs its median gain was 0.00% and 419 of
# them gained nothing at all, for a reservation of min(20% of budget, 40 s).  The same measurement
# also recorded THREE runs gaining over 5%, and those were treated as outliers.
#
# That is the same error this session already found and corrected once, in a different place.  The
# reported answer is a minimum over workers, so what pays is the LEFT TAIL, not the centre -- the
# argument that killed OGC_BEAMCAP's justification.  Scoring is ALSO per instance: a pass that
# earns nothing on seven instances and 27% on the eighth is worth its reservation on the eighth,
# and a median across all of them cannot see that.
#
# And the mono queue's "polish gains exactly 0.00%, confirmed on four cells" -- reported earlier
# today as corroboration -- is four cells drawn from the same distribution whose median is zero.
# It confirms the median, not the tail.
#
#     p0R1 / p0R2     polish OFF, as shipped today          <- reproduces the failed control
#     p1R1 / p1R2     polish ON                             <- does 2,796,522 come back?
#
# 60 s first because that is where the old number lives and the cells are cheap.  Then the same
# pair at 240 s, which is the budget that matters: the polish reservation is min(20%, 40 s), so at
# 240 s it costs 40 s of search and at 60 s only 12 s, and the trade is not the same one.
#
# prob_4 is included at 240 s because its answer is already 12.6% better than its best beam draw --
# operators other than the beam do the work there -- so it is the instance most likely to show the
# polish paying, and if the polish pays NOWHERE at 240 s that is the cleanest possible refutation.
set -u
cd "$(dirname "$0")/.." || exit 1
echo polishtail > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=polishtail" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/polishtail.log
mkdir -p results/audit; touch $L

run(){ # tag prob secs R env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $5 OGC_ROUNDS=$4 OGC_WSTAT=1 timeout $(( $3 * 5 )) \
        /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$2 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/polishtail.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: polishtail $tag" ) >/dev/null 2>&1
}

# the decisive pair, cheapest first
run "p1R2.16.60"  16  60 2 "OGC_POLISH=1"
run "p0R2.16.60"  16  60 2 ""
run "p1R1.16.60"  16  60 1 "OGC_POLISH=1"
run "p0R1.16.60"  16  60 1 ""
# the budget that actually ships
for rep in 1 2; do
    run "r$rep.p1.16.240" 16 240 1 "OGC_POLISH=1"
    run "r$rep.p0.16.240" 16 240 1 ""
    run "r$rep.p1.4.240"   4 240 1 "OGC_POLISH=1"
    run "r$rep.p0.4.240"   4 240 1 ""
    run "r$rep.p1.20.240" 20 240 1 "OGC_POLISH=1"
    run "r$rep.p0.20.240" 20 240 1 ""
    run "r$rep.p1.24.240" 24 240 1 "OGC_POLISH=1"
    run "r$rep.p0.24.240" 24 240 1 ""
    echo "REPDONE $rep" >> $L
done
echo "POLISHTAILDONE" >> $L
echo idle > harness/CURRENT
