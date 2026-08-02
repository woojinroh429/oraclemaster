#!/bin/bash
# IS THE CONTACT BOUND WHAT COSTS P5 ~120,000?
#
# Three clean P5 samples all sit above the 9,044,458 baseline -- 9,224,860 / 9,136,770 /
# 9,138,023 -- and the spread AMONG them (88,090) is smaller than the smallest gap TO the
# baseline (92,312).  That is what makes it a regression rather than variance: the current code
# is consistently parked above a number it used to reach, and has never once come back down.
#
# The bound is the newest and largest change, and it is the only one that can be switched off at
# RUNTIME without rebuilding, so it separates cleanly.  It provably does not change the beam's
# answer -- identical placement digests on P3/P4/P6 -- so if it costs P5 anything it does so by
# letting the search run FURTHER and arrive somewhere worse, which is a real effect and not a
# correctness problem.
#
# Three samples, because one would be indistinguishable from the 88,090 spread just measured.
#
#   bound off recovers ~9.04M  -> the bound is the cause; it stays only if P3's 1.85x is worth
#                                 P5's 1.3%, and that is a judgement to make with numbers in hand
#   bound off stays ~9.14M     -> the bound is exonerated and the cause is one of the other
#                                 changes since the baseline (build sweep, offset-relative
#                                 geometry, derived nent, the ask fix, the split budget bounds)
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

for r in 1 2 3; do
    f="results/p5_nobound_r$r.log"
    [ -s "$f" ] && continue
    echo "=== P5 bound OFF r$r $(date -u +%H:%M:%S)"
    OGC_NOPRUNE=1 BRK_DEBUG=1 timeout 3300 \
        python3.12 harness/run1.py myalgorithm 5 600 "P5 nobound r$r" > "$f" 2>&1
    tail -1 "$f"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/$f" >/dev/null 2>&1 \
      && git commit -q -m "P5 bound-off r$r" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
done
echo "p5bound done $(date -u +%H:%M:%S)"
