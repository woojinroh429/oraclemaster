#!/bin/bash
# Repeat the cohort on/off comparison.  One 180s beam, same axis, alternating so machine drift
# cannot favour one arm; then a floor sweep, then the other instances.
cd "$(dirname "$0")/.."
for r in 1 2 3; do
  for C in 0 1; do
    OGC_COHORT=$C python3.12 harness/beam1.py 6 180 "cohort=$C"
  done
done
for F in 0.0 0.15 0.5; do
  OGC_COHORT=1 OGC_COHORTF=$F python3.12 harness/beam1.py 6 180 "floor=$F"
done
for P in 4 3; do
  for C in 0 1; do
    OGC_COHORT=$C python3.12 harness/beam1.py $P 120 "cohort=$C"
  done
done
echo COHORT-DONE
