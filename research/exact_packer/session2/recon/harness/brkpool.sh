#!/bin/bash
# DOES GIVING brk A DIFFERENT INCUMBENT HELP?
#
# brk's improvement across the P3 logs ranges from 6,590 to 31,315 depending on which incumbent
# it receives -- a factor of five -- and a run draws 8 to 17 samples from that distribution, all
# from pool[0].  The specific incumbent worth 107,195 repacks to 83,095, and 80,795 has only ever
# been reached in runs where 83,095 was constructed.  So the question is whether widening where
# brk draws from finds that kind of point more often.
#
# THE RATE IS THE EXPERIMENT, not the idea.  Gain is credited only when pool[0] improves, so a
# repack of a lesser pool member usually scores zero and lowers brk's gain/spent, which makes the
# scheduler stop picking it.  Sample too often and the operator starves itself -- and the run
# would look like evidence against diversity when it is evidence about accounting.  So the sweep
# is over the rate, with 0.0 as the control that reproduces today's behaviour exactly.
#
# Three runs per arm on P3: one is worthless here because the quantity of interest is how OFTEN
# 80,795 is reached, which was 3 of 4 for the control.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

for rate in 0.0 0.34 0.5; do
  for r in 1 2 3; do
    tag=$(echo "$rate" | tr -d '.')
    f="results/bp_${tag}_r${r}.log"
    [ -s "$f" ] && continue
    OGC_BRKPOOL=$rate BRK_DEBUG=1 timeout 1500 \
        python3.12 harness/run1.py myalgorithm 3 240 "brkpool $rate r$r" > "$f" 2>&1
    echo "    $(grep -h '^P3 ' "$f" | tail -1)"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/$f" >/dev/null 2>&1 \
      && git commit -q -m "brkpool $rate r$r" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
  done
done
echo "brkpool done $(date -u +%H:%M:%S)"
