#!/bin/bash
# Is 70,000 a real number?  A capacity-aware lower bound, before another hour goes into chasing it.
#
# The assignment bound in the repo says 47,954 and does not know a bay can run out of room.  On
# P3 that is the binding constraint: 77 blocks name bay 0 first, they need 90,164 units of area
# x time, and bay 0 is 989 cells over an 82-step horizon = 81,098.  A ratio of 1.11 at perfect
# packing with the crane rule off.  Around eight blocks must leave bay 0 whatever anything does,
# and the median preference gap is 47, so several hundred Z3 units are structural.
#
# p3bound.py adds the capacity rows and keeps Z2 exact.  Both sides relax safely -- capacity
# over-estimates (cells x horizon, no crane rule, perfect tiling), demand under-estimates (true
# polygon area, minimised over orientations) -- so its optimum is a genuine lower bound.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1
[ -s results/p3bound.log ] || python3.12 harness/p3bound.py 3 180 > results/p3bound.log 2>&1
tail -20 results/p3bound.log
( cd .. && git add -f session2/recon/results/p3bound.log >/dev/null 2>&1 )
echo "queue11done  $(date -u +%H:%M:%S)"
