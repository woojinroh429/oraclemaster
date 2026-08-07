#!/bin/bash
# WHY DOES 240 s LOSE TO 60 s ON prob_16?  Decide it on the per-draw numbers.
#
# The fact to explain, both cells from the same build in the same queue, minutes apart:
#
#     P16 [d60.16]     60s  obj=3,472,568      ~10 beam draws across four workers
#     P16 [d240.16]   240s  obj=3,528,888      30 beam draws across four workers
#
# Three times the draws and a 1.6% WORSE answer.  opstat cannot separate the causes: it reports
# the beam's TOTAL gain, which is dominated by the first draw replacing the fallback (8.4e9), and
# every later draw books zero unless it beats the incumbent.
#
# OGC_DRAWSTAT=1 prints one line per draw -- wid, gen, TRUE axis index, seconds asked, seconds
# taken, objective returned.  Those numbers separate the three candidates:
#
#   H1  LATER DRAWS ARE WORSE.  Each worker holds a rotated view of all six axes and takes
#       axes[gen % 6], so a worker only reaches axes 4 and 5 once it gets past four draws --
#       which happens at 240 s and does NOT happen at 60 s.  Axis 4 carries w3mul=6.0, and the
#       w3 grid measured raising w3mul as harmful and saturating.  Signature: objective rising
#       with gen, and axes 4/5 worst in the per-axis table.
#
#   H2  THE DRAWS ARE NOT INDEPENDENT.  Thirty samples from a 30-38% wide distribution should
#       push the minimum well below ten samples' minimum; if it does not, the samples repeat.
#       Signature: few distinct objectives among the 30.
#
#   H3  EACH LONG DRAW IS INDIVIDUALLY WORSE.  The per-draw slice is resized from measured
#       runtime, so a 240 s run's draws are not obviously the same size as a 60 s run's.
#       Signature: the 60 s best draw beating every one of the 240 s draws.
#
# H1 and H3 are fixable and point in opposite directions -- H1 says stop spending late draws on
# bad axes, H3 says the width per draw is wrong.  H2 says neither and sends the budget to more
# workers instead.  Guessing between them is how this project has previously burned a day.
#
# prob_4 is the CONTRAST, and it is in the queue for a reason: its operator profile is the
# opposite of prob_16's.  On prob_4 pref earned 342,335 and 120,871 and bay earned 76,221 in
# 60 s cells, while on prob_16 bay spent 193.7 s across four workers to earn 3,759 in total.  Any
# conclusion drawn from prob_16 alone is a conclusion about prob_16.
#
# Three replicates per cell because a single draw sequence on prob_16 is worth nothing -- that is
# the whole finding this queue sits on.
#
# Read with:  python3.12 harness/drawread.py results/audit/drawstat.log
set -u
cd "$(dirname "$0")/.." || exit 1
echo drawstat > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=drawstat" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/drawstat.log
mkdir -p results/audit; touch $L

run(){ # tag prob secs
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_DRAWSTAT=1 OGC_OPSTAT=1 OGC_WSTAT=1 timeout $(( $3 * 5 )) \
        /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$2 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/drawstat.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: drawstat $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 16 4; do
        run "r$rep.s60.$p"  $p  60
        run "r$rep.s240.$p" $p 240
    done
    echo "REPDONE $rep" >> $L
done
echo "DRAWSTATDONE" >> $L
echo beamhard > harness/CURRENT
nohup bash harness/beamhard.sh >> results/beamhard.log 2>&1 < /dev/null &
