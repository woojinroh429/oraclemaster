#!/bin/bash
# brk RE-MEASURED WITH THE CALIBRATION FIXED.
#
# Every brk number recorded tonight was taken with half the pool's workers running an operator
# that had switched itself off.  The calibration halves its grid step until a build exceeds 0.25 s
# and then fits; a slow FIRST pack ends it with ONE point, and the single-point branch charged all
# of that time to the quadratic term --
#
#     brk calib: 474:458.1ms -> fixed 0.000s + 2.04e-06 s/col^2      against a real 6.5e-09
#
# 313x high, so the tier predictor declined every rung and opstat showed brk at 0.8 s and 0.0 s on
# two workers of a run where a calibrated worker did real work.  A single point may now set the
# rate only above 4000 columns; below that the seeded 6.4e-08 stands.
#
# So the adoption evidence -- prob_1 -6.52% over three replicates with no cell worse -- was
# measured with the operator half disabled.  This re-runs it.  Two outcomes are informative: a
# larger gain says the fix matters and the shipped zip is conservative, and an unchanged gain says
# the two workers that did calibrate were carrying it, which is worth knowing before any further
# work on this operator.
#
# prob_20 and prob_3 first because their controls are deterministic to the digit on this machine,
# so a pair there is a measurement rather than a draw; prob_1 next with three replicates because
# its answers sit in five discrete basins; prob_16 is excluded -- its controls spanned 2,519,071 to
# 3,030,292 tonight and all three arms of the last queue reversed between replicates.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo brkcal > harness/CURRENT
L=results/audit/brkcal.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/brkcal.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: brkcal $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 OGC_OPSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
for rep in 1 2; do
  for p in 20 3; do
    run "r$rep.p$p.off" $p 240 "OGC_BRK=0"
    run "r$rep.p$p.brk" $p 240 "OGC_BRK=1"
  done
done
echo "== BRKCAL deterministic instances done ==" >> $L
for rep in 1 2 3; do
  run "r$rep.p1.off" 1 240 "OGC_BRK=0"
  run "r$rep.p1.brk" 1 240 "OGC_BRK=1"
done
echo "== BRKCAL prob_1 done ==" >> $L
for rep in 1 2; do
  run "r$rep.p24.off" 24 240 "OGC_BRK=0"
  run "r$rep.p24.brk" 24 240 "OGC_BRK=1"
done
echo "BRKCALDONE" >> $L
echo idle > harness/CURRENT
