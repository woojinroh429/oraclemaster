#!/bin/bash
# CAP WHAT ONE BEAM DRAW MAY ASK FOR.  Does a budget spent on many narrow draws beat the same
# budget spent on fewer wide ones?
#
# Where this came from.  OGC_DRAWSTAT prints one line per beam draw; read within cell boundaries
# on prob_16:
#
#      60 s    8 draws at ask=11.2   best 3,557,431   median 5,472,182
#     240 s   20 draws at ask=47.2   best 3,656,247   median 5,634,552
#     240 s    1 draw  at ask= 9.3   best 3,602,025   <- the cell's best AND its reported answer
#
# The opening slice is 0.20 * budget for a search operator, so a bigger budget buys more draws AND
# bigger draws, and a draw's seconds turn into beam WIDTH (Bcur = min(Bmax, left/(per*rem)),
# recomputed per level from the slice it was handed).  The 240 s cell took 2.5x the draws at 4x
# the seconds each and returned a WORSE best while its MEDIAN draw improved 5.3%.  Wide draws are
# better on average and worse at the minimum -- and the minimum is what gets reported.
#
# What the cap does at each budget:
#
#     240 s   0.20*236 = 47.2 -> capped        ~40 narrow draws instead of ~20 wide ones
#      60 s   0.20*56  = 11.2 -> already under 12, NOTHING CHANGES
#
# That asymmetry is the point.  The evidence is a short-budget draw beating long-budget draws, so
# a fix that alters short-budget behaviour would be fitting the thing it was derived from.
#
#     base    as shipped
#     cap12   OGC_BEAMCAP=12    the measured-good slice size on prob_16
#     cap20   OGC_BEAMCAP=20    a middle rung -- if cap12 wins and cap20 does not, the effect is
#                               in the size and not merely in "more draws"
#
# INSTANCE SELECTION IS THE GUARD AGAINST FITTING prob_16.  prob_4 is in because it behaves the
# OPPOSITE way: its best beam draw is 3,160,713 against a final of 2,763,198, so 12.6% of its
# answer comes from operators this cap does not touch, and 240 s BEATS 60 s there (2,763,198 vs
# 2,959,655).  If the cap only helps prob_16 and costs prob_4, it is an instance-specific tweak
# and does not ship.  prob_20 and prob_24 are the neutral pair; prob_24 additionally repeats to
# the digit, so any movement there is the cap and not variance.
#
# Polish is OFF on every arm: it gained exactly 0.00% on all four mono cells.
#
# Read with:  python3.12 harness/beamside.py results/audit/beamcap.log base
set -u
cd "$(dirname "$0")/.." || exit 1
echo beamcap > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=beamcap" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/beamcap.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 OGC_OPSTAT=1 timeout 1200 /usr/bin/python3.12 harness/run1.py myalgorithm \
        $3 240 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/beamcap.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: beamcap $tag" ) >/dev/null 2>&1
}

# arm-major so the FIRST pass already covers every instance: if the run is cut short there is a
# complete base-vs-cap12 comparison rather than four arms on prob_16 and nothing else.
for rep in 1 2; do
    for p in 16 4 20 24; do
        run $rep base  $p ""
        run $rep cap12 $p "OGC_BEAMCAP=12"
        run $rep cap20 $p "OGC_BEAMCAP=20"
    done
    echo "REPDONE $rep" >> $L
done
echo "BEAMCAPDONE" >> $L
echo beamhard > harness/CURRENT
nohup bash harness/beamhard.sh >> results/beamhard.log 2>&1 < /dev/null &
