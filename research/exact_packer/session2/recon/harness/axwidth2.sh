#!/bin/bash
# IS THE 22% ABOUT AXIS 2's SCORING, OR ABOUT THE WIDTH IT WAS MEASURED AT?
#
# axis_work.md put axis 2 at 2,477,998 on prob_16 and flagged its own confound in the last
# paragraph: "The table is also at a fixed B=96, K=4, while `_worker` sizes each draw from the
# axis's own Bmul and K -- axis 2 runs at B=67, K=5 in production.  So 'axis 2 wins' may be a
# statement about the width rather than the scoring."
#
# Pinning the axis in production was just measured and it does NOT reproduce the number:
#
#     prob_16 240 s   stock 3,010,278     OGC_AXIS=2 2,932,602     -2.58%, against -21.6% offline
#
# Which is what the confound predicts.  OGC_AXIS=2 gives axis 2's ORDER and pos_lam and w3mul, but
# the width still comes from its own Bmul=0.7, so production runs it at B=67 while the table ran
# it at B=96.  _beam_width returns max(8, min(_BCAP, int(mul * _BCAP))), so for Bmul=0.7 the way
# to reach 96 is _BCAP = 137.
#
#     OGC_AXIS=2 OGC_BCAP=137   ->   axis 2 scoring at B=96, the table's width
#
# K CANNOT BE MATCHED FROM THE ENVIRONMENT.  The table used K=4 and axis 2 carries K=5; K is read
# straight from the axis dict with no override.  So this closes the width half of the confound and
# leaves the K half open -- if B=96 recovers most of the 22%, K is a detail; if it recovers none,
# K or the offline/production path difference is carrying it.
#
# THE OTHER READING THIS TESTS.  myalgorithm.py's OGC_BEAMCAP comment measured the opposite
# direction on this same instance -- wider draws better on average, worse at the minimum, "and the
# minimum is what gets reported".  If that is the dominant effect then raising BCAP should HURT,
# and the offline table's B=96 win has to come from somewhere else entirely.  Both cells below run
# stock-axis as well as pinned-axis so the width move is priced with and without concentration.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo axwidth2 > harness/CURRENT
L=results/audit/axwidth2.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/axwidth2.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/axwidth2.sh \
        && git commit -q -m "in-flight: axwidth2 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_WSTAT=1 timeout 560 /usr/bin/python3.12 harness/run1.py myalgorithm $2 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  run "w.ax2b96.r$rep"  16 "WORKERS=4 OGC_AXIS=2 OGC_BCAP=137"
  run "w.b96.r$rep"     16 "WORKERS=4 OGC_BCAP=137"
done
echo "AXWIDTH2DONE" >> $L
echo idle > harness/CURRENT
