#!/bin/bash
# Now that the build is 1.43x faster, does the outsider list finally fit at double width?
#
# NOUT=40 is not a tuned value, it is what the deadline allowed.  Measured before the parallel
# build: doubling it was worth -0.38% on prob_26 and -0.68% on prob_36 and saturated by x2 (x3
# returned x2's answer exactly), but prob_13 then took 331 s of a 180 s budget -- 1.84x -- and an
# overrun scores -1 whatever the objective says.  The file's own conclusion was that widening
# safely needs a FASTER BUILD rather than a bigger table.
#
# The build is now parallel and the overrun audit just came back clean at 180 s (max 180 s, ten
# instances, no overrun).  So the same experiment is worth exactly one more run -- and the
# RUNTIME is the primary reading, not the objective.
#
# Instances chosen where NOUT actually binds: 300-block ones, where 40 covers 31-70% of the
# profitable entrants.  prob_13 is the one that overran, so it leads.
cd "$(dirname "$0")/.."
L=results/audit/noutwide.log; : > $L
for p in 13 26 36 25 30 40 23 12; do
  for a in 1 2; do
    OGC_TIERNOUT=$a /usr/bin/python3.12 harness/run1.py myalgorithm $p 180 "nout x$a" \
        --data data/stage2 >> $L 2>&1
  done
done
echo NOUTDONE >> $L
