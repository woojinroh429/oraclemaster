#!/bin/bash
cd "$(dirname "$0")/.."
for T in 120 240 480 900 1500; do python3.12 harness/run1.py myalg_v2 6 $T; done
for T in 120 240 480 900; do python3.12 harness/run1.py myalg_v2 4 $T; done
for T in 60 120 240 480; do python3.12 harness/run1.py myalg_v2 3 $T; done
echo LADDER-DONE
