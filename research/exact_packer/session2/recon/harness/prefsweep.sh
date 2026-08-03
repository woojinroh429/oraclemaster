#!/bin/bash
# Three arms, forty paired instances, judged by sign count.
#
#   full   shipped roster, shipped classification            (control)
#   pref   OGC_PREFSEARCH=1 -- pref treated as the search operator it is
#   lean   pref as search AND bay/brk dropped, so the 26% they hold goes to the rest
#
# `lean` is the configuration the reasoning favours: w2*Z2 is a median 0.5% of the objective on
# this set and bay exists to chase it, while w3*Z3 is a median 39.5% and pref is the only
# operator aiming there.  The 10-instance ablation says removal alone is neutral (5-5, mean
# -0.07%), so removal is an ARM here rather than a decision.
#
# Interleaved per instance so a slow patch of machine hits all three alike.  180 s, four
# workers, python3.12 -- the shipped configuration and the engine every log in results/ was
# made on.
cd "$(dirname "$0")/.."
L=results/audit/prefsweep.log; : > $L
for p in $(seq 1 40); do
  OGC_PREFSEARCH=  OGC_OPS=                      /usr/bin/python3.12 harness/run1.py myalgorithm $p 180 full >> $L 2>&1 --data data/stage2
  OGC_PREFSEARCH=1 OGC_OPS=                      /usr/bin/python3.12 harness/run1.py myalgorithm $p 180 pref >> $L 2>&1 --data data/stage2
  OGC_PREFSEARCH=1 OGC_OPS=beam,grow,bal,pref    /usr/bin/python3.12 harness/run1.py myalgorithm $p 180 lean >> $L 2>&1 --data data/stage2
done
echo PREFSWEEPDONE >> $L
