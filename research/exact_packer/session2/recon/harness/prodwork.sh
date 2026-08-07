#!/bin/bash
# HOW MUCH WORK DOES A PRODUCTION BEAM DRAW ACTUALLY DO?
#
# Everything the work-mode campaign concluded hangs on this one number, and it has never been
# measured -- only estimated, as 14 s of observed draw time at the ~220 expansions/s that beam1
# shows on prob_16.  The measured table says a draw's quality depends on it sharply:
#
#     prob_16, winning axis      3,000 work -> 3,159,373      6,000 work -> 2,477,998
#
# Three different prescriptions follow from three possible true values, and two of them contradict
# what this session already decided:
#
#     ~3,000    the estimate holds.  Draws are at half the optimum on prob_16, and since neither
#               width (closed: 26 of 29 paired cells identical from B=48 to B=96) nor seconds (a
#               draw is handed 47.2 s and returns in 14) is binding, something else stops a draw
#               there and has to be found before anything can be prescribed.
#
#     ~6,000    prob_16 is ALREADY at its optimum.  The -22% seen in work space is then not
#               reachable by resizing draws at all, and the whole direction closes -- the gap would
#               be elsewhere in the pipeline (the min over workers, the operator loop, the polish).
#
#     >>6,000   draws are past the bottom of the U, and the fix is to make them SMALLER.  That
#               revives OGC_BEAMCAP, which this session killed on the grounds that prob_16 wants
#               larger draws.  It would mean that reasoning was backwards.
#
# So this is measured before anything else is built.  OGC_BEAMSTAT=1 now prints work= per draw
# from the engine's own counter; the rest of the line (salv/capped/used/level/B/K) says whether the
# draw ran out of time, hit the width ceiling, or finished early, which is what identifies the
# binding constraint in the ~3,000 case.
#
# Real 240 s runs of the shipped path -- four workers, operator loop, polish -- not beam1.  Two
# replicates because the wall-clock noise is back here: this is the regime where prob_16 spans
# 19.6%.  The work figures are what matter and they are read per draw, not per run.
set -u
cd "$(dirname "$0")/.." || exit 1
echo prodwork > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=prodwork" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/prodwork.log
mkdir -p results/audit; touch $L

for rep in 1 2; do
  for p in 16 4 24; do
    tag="r$rep.$p"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && continue
    echo "# [$tag]" >> $L
    OGC_BEAMSTAT=1 OGC_WSTAT=1 OGC_OPSTAT=1 timeout 1200 \
        /usr/bin/python3.12 harness/run1.py myalgorithm $p 240 "[$tag]" --data data/stage2 \
        >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/prodwork.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: prodwork $tag" ) >/dev/null 2>&1
  done
done
echo "PRODWORKDONE" >> $L
echo idle > harness/CURRENT
